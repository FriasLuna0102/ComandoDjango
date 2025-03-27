import time
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Deteccion
from .api.serializers import DeteccionSerializer, ImagenUploadSerializer
from .services.Robo_Services import RoboflowService
from .services.yolo_service import YOLOService
from .services.c_service import ClaudeService

from PIL import Image
import logging

logger = logging.getLogger(__name__)


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

        # Cargar imagen con PIL
        try:
            imagen_pil = Image.open(imagen_file)
        except Exception as e:
            return Response(
                {'error': f'Error al abrir la imagen: {str(e)}'},
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
                center=center_instance  # Ahora center_instance ya está definido
            )

            # Guardar los resultados en Deteccion
            deteccion.set_resultados(resultados)
            deteccion.save()

            # Variable para almacenar la referencia a la imagen guardada en el segundo modelo
            imagen_guardada = None

            # Guardar también en el modelo Image si se solicita
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
                'resultados': resultados
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
