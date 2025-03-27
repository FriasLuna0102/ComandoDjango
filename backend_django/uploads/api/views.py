from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend

from center.api.serializer import CenterSerializer
from center.models import Center
from deteccion_app.models import Deteccion
from uploads.api.serializers import DeteccionBriefSerializer, ImageSerializer
from uploads.models import Image

class ImageViewSet(viewsets.ModelViewSet):
    """
    API endpoint para gestionar imágenes
    """
    serializer_class = ImageSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['center', 'processed']
    ordering_fields = ['taken_at']

    def get_queryset(self):
        """Filtra las imágenes según el usuario"""
        user = self.request.user
        # Si el usuario no es superusuario, solo ve imágenes de su centro
        if not user.is_superuser and hasattr(user, 'center'):
            return Image.objects.filter(center=user.center)
        return Image.objects.all()

    @action(detail=False, methods=['GET'])
    def by_center(self, request):
        """
        Obtiene todas las imágenes agrupadas por centro
        """
        # Verificar si se solicita un centro específico
        center_id = request.query_params.get('center_id')

        queryset = self.get_queryset()
        if center_id:
            queryset = queryset.filter(center_id=center_id)

        # Agrupar por centro
        centers = {}
        for image in queryset:
            center_id = str(image.center_id)
            if center_id not in centers:
                centers[center_id] = {
                    'center_id': image.center_id,
                    'center_name': image.center.name if image.center else 'Sin centro',
                    'images': []
                }

            # Serializar la imagen
            serializer = self.get_serializer(image)
            centers[center_id]['images'].append(serializer.data)

        return Response(list(centers.values()))

    @action(detail=True, methods=['GET'])
    def detecciones(self, request, pk=None):
        """
        Obtiene todas las detecciones asociadas a una imagen
        """
        image = self.get_object()

        # Intentar buscar por nombre de archivo
        file_path = str(image.file)
        detecciones = Deteccion.objects.filter(imagen__contains=file_path)

        # Si no hay resultados, verificar si hay datos en metadata
        if not detecciones.exists() and image.metadata:
            # Crear un objeto de tipo diccionario con la estructura esperada
            deteccion_data = {
                'id': str(image.id),
                'fecha_creacion': image.taken_at.isoformat(),
                'tipo_modelo': image.metadata.get('model_type', 'unknown'),
                'resultados': image.metadata,
                'numero_objetos': len(image.metadata.get('detections', []))
            }
            return Response([deteccion_data])

        serializer = DeteccionBriefSerializer(detecciones, many=True)
        return Response(serializer.data)


class CenterViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint para consultar centros
    """
    queryset = Center.objects.all()
    serializer_class = CenterSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=True, methods=['GET'])
    def images(self, request, pk=None):
        """
        Obtiene todas las imágenes de un centro específico
        """
        center = self.get_object()
        images = Image.objects.filter(center=center)

        # Filtra por processed si se especifica
        processed = request.query_params.get('processed')
        if processed is not None:
            images = images.filter(processed=(processed.lower() == 'true'))

        serializer = ImageSerializer(images, many=True)
        return Response(serializer.data)
