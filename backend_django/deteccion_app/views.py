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
        # Obtener la información EXIF
        if hasattr(img, '_getexif') and img._getexif() is not None:
            exif = dict((ExifTags.TAGS.get(k, k), v) for k, v in img._getexif().items())

            # Encontrar la orientación
            if 'Orientation' in exif:
                orientation = exif['Orientation']

                # Aplicar transformaciones según la orientación
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


def prepare_image_for_model(img_file):
    """
    Prepara la imagen para el procesamiento con el modelo:
    - Corrige la orientación
    - Asegura el formato correcto
    - Preserva la calidad sin redimensionar innecesariamente
    """
    try:
        # Abrir imagen con PIL
        img = Image.open(img_file)

        # Si la imagen tiene transparencia, convertir a RGB rellenando con blanco
        if img.mode == 'RGBA':
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[3])  # Canal alfa
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        # Corregir orientación basada en EXIF
        img = fix_image_orientation(img)

        # Verificar si necesitamos redimensionar (solo si la imagen es muy grande)
        width, height = img.size
        max_dimension = 1920  # Límite razonable que mantiene buena calidad

        if width > max_dimension or height > max_dimension:
            # Calcular nueva dimensión preservando proporción
            if width > height:
                new_width = max_dimension
                new_height = int(height * max_dimension / width)
            else:
                new_height = max_dimension
                new_width = int(width * max_dimension / height)

            logger.info(f"Redimensionando imagen de {width}x{height} a {new_width}x{new_height}")
            img = img.resize((new_width, new_height), Image.LANCZOS)

        logger.info(f"Imagen preparada: {img.size[0]}x{img.size[1]}, modo: {img.mode}")
        return img

    except Exception as e:
        logger.error(f"Error al preparar la imagen: {e}")
        raise


class DeteccionViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet para listar y recuperar detecciones"""

    queryset = Deteccion.objects.all()
    serializer_class = DeteccionSerializer

    # En tu clase DeteccionViewSet
    @action(detail=False, methods=['post'], url_path='analizar')
    def analizar_imagen(self, request):
        """
        Analiza una imagen usando el modelo seleccionado
        """
        serializer = ImagenUploadSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        imagen_file = serializer.validated_data['imagen']
        tipo_modelo = serializer.validated_data['tipo_modelo']
        guardar_imagen = serializer.validated_data['guardar_imagen']

        # Campos opcionales para el modelo Image
        center_id = serializer.validated_data.get('center_id', None)
        lighting_condition = serializer.validated_data.get('lighting_condition', '')
        metadata = serializer.validated_data.get('metadata', {})

        # Cargar y preparar imagen con PIL
        try:
            imagen_pil = prepare_image_for_model(imagen_file)

            # Guardar información sobre la imagen para debugging
            logger.info(f"Imagen cargada: {imagen_pil.size[0]}x{imagen_pil.size[1]}, "
                        f"modo: {imagen_pil.mode}, formato: {imagen_file.content_type}")
        except Exception as e:
            return Response(
                {'error': f'Error al procesar la imagen: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Seleccionar el servicio de modelo apropiado
        if tipo_modelo == 'yolo':
            modelo_service = YOLOService()
        elif tipo_modelo == 'cl':
            modelo_service = ClaudeService()
        elif tipo_modelo == 'roboflow':
            modelo_service = RoboflowService()
        else:
            return Response(
                {'error': f'Tipo de modelo no soportado: {tipo_modelo}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Procesar la imagen
        try:
            start_time = time.time()
            modelo_service.load_model()  # Asegurarse de que el modelo esté cargado
            resultados = modelo_service.process_image(imagen_pil)
            tiempo_procesamiento = time.time() - start_time

            # Log de resultados para debugging
            detections_count = len(resultados.get('detections', []))
            logger.info(f"Detecciones encontradas: {detections_count}")

            # Si no hay detecciones, registrar más información
            if detections_count == 0:
                logger.warning(f"No se encontraron detecciones. Modelo: {tipo_modelo}, "
                               f"Tiempo: {tiempo_procesamiento:.2f}s")

            # Obtener el centro antes de crear la detección
            # Importar modelos necesarios
            from uploads.models import Image as ImageModel
            from center.models import Center
            from django.utils import timezone

            # Verificar si hay centros disponibles
            center_instance = None
            center_count = Center.objects.count()
            logger.info(f"Número de centros disponibles: {center_count}")

            if center_id:
                try:
                    center_instance = Center.objects.get(id=center_id)
                    logger.info(f"Centro encontrado con ID: {center_id}")
                except Center.DoesNotExist:
                    logger.warning(f"Centro con ID {center_id} no encontrado")

            # Si no hay centro específico, buscar uno existente o crear uno nuevo
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

            # Crear registro en la base de datos Deteccion
            deteccion = Deteccion(
                tipo_modelo=tipo_modelo,
                tiempo_procesamiento=tiempo_procesamiento,
                center=center_instance,
                confirmed=False  # Inicialmente no está confirmado
            )

            # Guardar los resultados en Deteccion
            deteccion.set_resultados(resultados)
            deteccion.save()

            # Variable para almacenar la referencia a la imagen guardada en el segundo modelo
            imagen_guardada = None

            # Guardar también en el modelo Image solo si se solicita
            if guardar_imagen:
                try:
                    # Si no se proporciona metadata, usar los resultados de la detección
                    if not metadata:
                        metadata = resultados

                    # Crear instancia del modelo Image
                    imagen_guardada = ImageModel(
                        file=imagen_file,
                        taken_at=timezone.now(),
                        taken_by=request.user if request.user.is_authenticated else None,
                        center=center_instance,
                        processed=True,
                        lighting_condition=lighting_condition or '',
                        metadata=metadata
                    )

                    # Guardar la imagen
                    imagen_guardada.save()
                    logger.info(f"Imagen guardada exitosamente en modelo Image con ID: {imagen_guardada.id}")

                    # Actualizar la referencia a la imagen en la detección
                    deteccion.image = imagen_guardada
                    deteccion.save(update_fields=['image'])

                except Exception as img_error:
                    logger.error(f"Error al guardar en el modelo Image: {str(img_error)}", exc_info=True)
                    # Continuar con el proceso aunque falle el guardado en Image

            # Construir la respuesta
            response_data = {
                'deteccion_id': deteccion.id,
                'tiempo_procesamiento': tiempo_procesamiento,
                'resultados': resultados,
                'confirmed': deteccion.confirmed,
            }

            # Añadir información de la imagen guardada en Image si existe
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
        # Opcionalmente podríamos recibir cambios en los resultados si el usuario los modificó
        resultados_modificados = serializer.validated_data.get('resultados_modificados', None)

        try:
            # Buscar la detección previamente guardada
            deteccion = Deteccion.objects.get(id=analysis_id)

            # Si se proporcionaron resultados modificados, actualizarlos
            if resultados_modificados:
                deteccion.set_resultados(resultados_modificados)
                deteccion.save()

            # Procesar la imagen si es necesario
            imagen_file = serializer.validated_data.get('imagen', None)
            guardar_imagen = serializer.validated_data.get('guardar_imagen', True)
            center_id = serializer.validated_data.get('center_id', None)

            # Variables para el modelo Image
            imagen_guardada = None

            # Si tenemos una imagen y queremos guardarla
            if imagen_file and guardar_imagen:
                try:
                    from uploads.models import Image as ImageModel
                    from center.models import Center
                    from django.utils import timezone

                    # Obtener el centro
                    center_instance = None
                    if center_id:
                        try:
                            center_instance = Center.objects.get(id=center_id)
                        except Center.DoesNotExist:
                            pass

                    # Si no hay centro específico, usar el de la detección
                    if not center_instance:
                        center_instance = deteccion.center

                    # Crear y guardar la imagen
                    imagen_guardada = ImageModel(
                        file=imagen_file,
                        taken_at=timezone.now(),
                        taken_by=request.user if request.user.is_authenticated else None,
                        center=center_instance,
                        processed=True,
                        metadata=deteccion.get_resultados()
                    )

                    imagen_guardada.save()

                    # Actualizar la referencia en la detección
                    deteccion.image = imagen_guardada
                    deteccion.confirmed = True  # Marcar como confirmada
                    deteccion.save(update_fields=['image', 'confirmed'])

                except Exception as img_error:
                    logger.error(f"Error al guardar imagen confirmada: {str(img_error)}", exc_info=True)

            # Serializar la detección para la respuesta
            deteccion_serializer = DeteccionSerializer(deteccion)
            response_data = deteccion_serializer.data

            # Añadir información de la imagen guardada si existe
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
            # Filtrar detecciones por centro directamente
            detecciones = Deteccion.objects.filter(center_id=center_id)
            serializer = self.get_serializer(detecciones, many=True)
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Error al obtener detecciones por centro: {str(e)}", exc_info=True)
            return Response(
                {'error': f'Error al obtener detecciones: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
