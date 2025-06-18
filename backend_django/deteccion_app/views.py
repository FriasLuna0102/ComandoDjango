import time
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Deteccion
from .api.serializers import DeteccionSerializer, ImagenUploadSerializer, ConfirmAnalysisSerializer
from .services.Robo_Services import RoboflowService
from .services.yolo_service import YOLOService
from .services.c_service import ClaudeService

from PIL import Image, ImageOps, ExifTags
import logging

logger = logging.getLogger(__name__)


def fix_image_orientation(img):
    """
    Corrige la orientación de la imagen basándose en los datos EXIF
    """
    try:
        if hasattr(img, '_getexif') and img._getexif() is not None:
            exif = dict((ExifTags.TAGS.get(k, k), v) for k, v in img._getexif().items())

            if 'Orientation' in exif:
                orientation = exif['Orientation']

                if orientation == 2:
                    img = img.transpose(Image.FLIP_LEFT_RIGHT)
                elif orientation == 3:
                    img = img.rotate(180)
                elif orientation == 4:
                    img = img.rotate(180).transpose(Image.FLIP_LEFT_RIGHT)
                elif orientation == 5:
                    img = img.rotate(-90, expand=True).transpose(Image.FLIP_LEFT_RIGHT)
                elif orientation == 6:
                    img = img.rotate(-90, expand=True)
                elif orientation == 7:
                    img = img.rotate(90, expand=True).transpose(Image.FLIP_LEFT_RIGHT)
                elif orientation == 8:
                    img = img.rotate(90, expand=True)

        return img
    except Exception as e:
        logger.warning(f"Error al corregir la orientación: {e}")
        return img


# def prepare_image_for_model(img_file):
#     """
#     Prepara la imagen para el procesamiento con el modelo:
#     - Corrige la orientación
#     - Asegura el formato correcto
#     - Preserva la calidad sin redimensionar innecesariamente
#     """
#     try:
#         img = Image.open(img_file)
#
#         if img.mode == 'RGBA':
#             background = Image.new('RGB', img.size, (255, 255, 255))
#             background.paste(img, mask=img.split()[3])  # Canal alfa
#             img = background
#         elif img.mode != 'RGB':
#             img = img.convert('RGB')
#
#         img = fix_image_orientation(img)
#
#         width, height = img.size
#         max_dimension = 640
#         if max(width, height) > max_dimension:
#             scale = max_dimension / max(width, height)
#             new_size = (int(width * scale), int(height * scale))
#             img = img.resize(new_size, Image.LANCZOS)
#
#         logger.info(f"Imagen preparada: {img.size[0]}x{img.size[1]}, modo: {img.mode}")
#         return img
#
#     except Exception as e:
#         logger.error(f"Error al preparar la imagen: {e}")
#         raise


def prepare_image_for_model(img_file):
    img = Image.open(img_file)

    # Convertir a RGB si hace falta
    if img.mode == 'RGBA':
        bg = Image.new('RGB', img.size, (255,255,255))
        bg.paste(img, mask=img.split()[3])
        img = bg
    elif img.mode != 'RGB':
        img = img.convert('RGB')

    img = fix_image_orientation(img)

    # **Stretch** a 720×720 px (distorsión intencionada)
    img = img.resize((870, 870), Image.LANCZOS)

    logger.info(f"Imagen preparada ESTIRADA: {img.size[0]}x{img.size[1]}, modo: {img.mode}")
    return img


class DeteccionViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet para listar y recuperar detecciones"""

    queryset = Deteccion.objects.all()
    serializer_class = DeteccionSerializer

    @action(detail=False, methods=['post'], url_path='analizar')
    def analizar_imagen(self, request):
        """
        Analiza una imagen usando el modelo seleccionado
        """
        print("Request recibido:", request.data)
        serializer = ImagenUploadSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        imagen_file = serializer.validated_data['imagen']
        tipo_modelo = serializer.validated_data['tipo_modelo']
        guardar_imagen = serializer.validated_data['guardar_imagen']

        center_id = serializer.validated_data.get('center_id', None)
        lighting_condition = serializer.validated_data.get('lighting_condition', '')
        metadata = serializer.validated_data.get('metadata', {})

        try:
            imagen_pil = prepare_image_for_model(imagen_file)

            logger.info(f"Imagen cargada: {imagen_pil.size[0]}x{imagen_pil.size[1]}, "
                        f"modo: {imagen_pil.mode}, formato: {imagen_file.content_type}")
        except Exception as e:
            return Response(
                {'error': f'Error al procesar la imagen: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if tipo_modelo == 'yolo':
            modelo_service = YOLOService()
        elif tipo_modelo == 'cl':
            modelo_service = ClaudeService()
        elif tipo_modelo == 'rf_detr':
            modelo_service = RoboflowService()
            resultados_rf = modelo_service.process_image(imagen_pil)
            if resultados_rf.get('output_image'):

                imagen_file = resultados_rf['output_image']
                # print("Imagen procesada:", imagen_file)
        else:
            return Response(
                {'error': f'Tipo de modelo no soportado: {tipo_modelo}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            start_time = time.time()
            modelo_service.load_model()
            resultados = modelo_service.process_image(imagen_pil)
            tiempo_procesamiento = time.time() - start_time

            detections_count = len(resultados.get('detections', []))
            logger.info(f"Detecciones encontradas: {detections_count}")

            if detections_count == 0:
                logger.warning(f"No se encontraron detecciones. Modelo: {tipo_modelo}, "
                               f"Tiempo: {tiempo_procesamiento:.2f}s")

            from uploads.models import Image as ImageModel
            from center.models import Center
            from django.utils import timezone

            center_instance = None
            center_count = Center.objects.count()
            logger.info(f"Número de centros disponibles: {center_count}")

            if center_id:
                try:
                    center_instance = Center.objects.get(id=center_id)
                    logger.info(f"Centro encontrado con ID: {center_id}")
                except Center.DoesNotExist:
                    logger.warning(f"Centro con ID {center_id} no encontrado")

            if not center_instance:
                center_instance = Center.objects.first()

                # Si no hay centros, crear uno por defecto
                if not center_instance:
                    logger.info("Creando nuevo centro por defecto")
                    center_instance = Center.objects.create(
                        name="Centro de Acopio Automático",
                        address="Dirección por defecto"
                    )
                    logger.info(f"Centro creado automáticamente con ID: {center_instance.id}")

            deteccion = Deteccion(
                tipo_modelo=tipo_modelo,
                tiempo_procesamiento=tiempo_procesamiento,
                center=center_instance,
                confirmed=False  # Inicialmente no está confirmado
            )

            deteccion.set_resultados(resultados)
            deteccion.save()

            imagen_guardada = None

            if guardar_imagen:
                try:
                    if not metadata:
                        metadata = resultados

                    print("Guardando imagen en modelo Image...:", imagen_file)
                    imagen_guardada = ImageModel(
                        file=imagen_file,
                        taken_at=timezone.now(),
                        taken_by=request.user if request.user.is_authenticated else None,
                        center=center_instance,
                        processed=True,
                        lighting_condition=lighting_condition or '',
                        metadata=metadata
                    )

                    imagen_guardada.save()
                    logger.info(f"Imagen guardada exitosamente en modelo Image con ID: {imagen_guardada.id}")

                    # Actualizar la referencia a la imagen en la detección
                    deteccion.image = imagen_guardada
                    deteccion.save(update_fields=['image'])

                except Exception as img_error:
                    logger.error(f"Error al guardar en el modelo Image: {str(img_error)}", exc_info=True)

            response_data = {
                'deteccion_id': deteccion.id,
                'tiempo_procesamiento': tiempo_procesamiento,
                'resultados': resultados,
                'confirmed': deteccion.confirmed,
            }

            if imagen_guardada:
                response_data['imagen_guardada'] = {
                    'id': imagen_guardada.id,
                    'url': request.build_absolute_uri(imagen_guardada.file.url) if hasattr(imagen_guardada.file,
                                                                                           'url') else None
                }

            return Response(response_data)

        except Exception as e:
            logger.error(f"Error al procesar la imagen: {str(e)}", exc_info=True)
            return Response(
                {'error': f'Error al procesar la imagen: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'], url_path='confirmar')
    def confirmar_analisis(self, request):
        """
        Confirma y guarda los resultados de análisis previamente realizados
        """
        serializer = ConfirmAnalysisSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        analysis_id = serializer.validated_data['analysis_id']
        resultados_modificados = serializer.validated_data.get('resultados_modificados', None)

        try:
            from uploads.models import Image as ImageModel
            from center.models import Center
            from django.utils import timezone
            from django.core.files.base import ContentFile
            import base64

            deteccion = Deteccion.objects.get(id=analysis_id)

            if resultados_modificados:
                deteccion.set_resultados(resultados_modificados)
                deteccion.save()

            imagen_file = serializer.validated_data.get('imagen', None)
            imagen_pil = prepare_image_for_model(imagen_file)

            modelo_service = RoboflowService()
            resultados_rf = modelo_service.process_image(imagen_pil)

            center_id = serializer.validated_data.get('center_id', None)

            if center_id:
                try:
                    center_instance = Center.objects.get(id=center_id)
                except Center.DoesNotExist:
                    center_instance = deteccion.center
            else:
                center_instance = deteccion.center

            guardar_imagen = serializer.validated_data.get('guardar_imagen', True)
            imagen_guardada = None

            if resultados_rf.get('output_image'):
                imagen_file = resultados_rf['output_image']
                # print("Imagen procesada 22222:", imagen_file)

                if imagen_file and guardar_imagen:
                    try:
                        # Si la imagen está en base64
                        if isinstance(imagen_file, str):
                            if ',' in imagen_file:
                                imagen_file = imagen_file.split(',')[1]
                            imagen_data = base64.b64decode(imagen_file)
                            imagen_content = ContentFile(imagen_data)
                            nombre_archivo = f"roboflow_output_{int(time.time())}.png"

                            imagen_guardada = ImageModel(
                                taken_at=timezone.now(),
                                taken_by=request.user if request.user.is_authenticated else None,
                                center=center_instance,
                                processed=True,
                                metadata=deteccion.get_resultados()
                            )
                            imagen_guardada.file.save(nombre_archivo, imagen_content, save=False)
                            imagen_guardada.save()

                            deteccion.image = imagen_guardada
                            deteccion.confirmed = True
                            deteccion.save(update_fields=['image', 'confirmed'])

                    except Exception as img_error:
                        logger.error(f"Error al guardar imagen confirmada: {str(img_error)}", exc_info=True)

            deteccion_serializer = DeteccionSerializer(deteccion)
            response_data = deteccion_serializer.data

            if imagen_guardada:
                response_data['imagen_guardada'] = {
                    'id': imagen_guardada.id,
                    'url': request.build_absolute_uri(imagen_guardada.file.url) if hasattr(imagen_guardada.file,
                                                                                           'url') else None
                }

            return Response(response_data)

        except Deteccion.DoesNotExist:
            return Response(
                {'error': f'Análisis con ID {analysis_id} no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error al confirmar análisis: {str(e)}", exc_info=True)
            return Response(
                {'error': f'Error al confirmar análisis: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'], url_path='info-modelo')
    def info_modelo(self, request):
        """
        Devuelve información sobre los modelos disponibles
        """
        tipo_modelo = request.query_params.get('tipo', 'yolo')

        try:
            if tipo_modelo == 'yolo':
                modelo_service = YOLOService()
            elif tipo_modelo == 'cl':
                modelo_service = ClaudeService()
            else:
                return Response(
                    {'error': f'Tipo de modelo no soportado: {tipo_modelo}'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            modelo_service.load_model()
            info = modelo_service.get_model_info()

            return Response(info)

        except Exception as e:
            logger.error(f"Error al obtener información del modelo: {str(e)}", exc_info=True)
            return Response(
                {'error': f'Error al obtener información del modelo: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'], url_path='by-center')
    def detecciones_by_center(self, request):
        """
        Obtiene las detecciones de un centro específico
        """
        center_id = request.query_params.get('center_id')

        if not center_id:
            return Response(
                {'error': 'Debe proporcionar un center_id'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            detecciones = Deteccion.objects.filter(center_id=center_id)
            serializer = self.get_serializer(detecciones, many=True)
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Error al obtener detecciones por centro: {str(e)}", exc_info=True)
            return Response(
                {'error': f'Error al obtener detecciones: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
