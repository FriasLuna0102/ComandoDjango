from rest_framework import serializers
from ..models import Deteccion


class DeteccionSerializer(serializers.ModelSerializer):
    """Serializador para el modelo de Detección"""

    resultados = serializers.SerializerMethodField()
    center_id = serializers.IntegerField(source='center.id', read_only=True, allow_null=True)
    image_id = serializers.IntegerField(source='image.id', read_only=True, allow_null=True)

    class Meta:
        model = Deteccion
        fields = ['id', 'fecha_creacion', 'tipo_modelo', 'numero_objetos',
                  'tiempo_procesamiento', 'resultados', 'center_id', 'image_id', 'confirmed']
        read_only_fields = ['id', 'fecha_creacion', 'numero_objetos',
                            'tiempo_procesamiento', 'resultados', 'center_id', 'image_id', 'confirmed']

    def get_resultados(self, obj):
        """Obtiene los resultados como diccionario"""
        return obj.get_resultados()


class ImagenUploadSerializer(serializers.Serializer):
    """Serializador para la subida de imágenes"""

    imagen = serializers.ImageField()
    tipo_modelo = serializers.ChoiceField(
        choices=[
            ('yolo', 'YOLO'),
            ('cl', 'Yolo_2.0'),
            ('rf_detr', 'RF_DETR')
        ]
    )
    guardar_imagen = serializers.BooleanField(default=False)

    # Campos opcionales del modelo Image
    center_id = serializers.IntegerField(required=False)
    lighting_condition = serializers.CharField(max_length=50, required=False, allow_blank=True)
    metadata = serializers.JSONField(required=False, default=dict)


class ConfirmAnalysisSerializer(serializers.Serializer):
    """Serializador para confirmar un análisis previamente realizado"""

    analysis_id = serializers.CharField(required=True)
    imagen = serializers.ImageField(required=False)
    guardar_imagen = serializers.BooleanField(default=True)
    center_id = serializers.IntegerField(required=False)
    resultados_modificados = serializers.JSONField(required=False)
