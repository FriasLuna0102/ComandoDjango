from rest_framework import serializers

from center.models import Center
from deteccion_app.models import Deteccion
from uploads.models import Image


class DeteccionBriefSerializer(serializers.ModelSerializer):
    """Serializer simplificado para detecciones"""
    resultados = serializers.SerializerMethodField()

    class Meta:
        model = Deteccion
        fields = ['id', 'fecha_creacion', 'tipo_modelo', 'resultados', 'numero_objetos']

    def get_resultados(self, obj):
        """Obtiene los resultados como diccionario Python"""
        return obj.get_resultados()


class ImageSerializer(serializers.ModelSerializer):
    """Serializer para el modelo Image"""
    detecciones = DeteccionBriefSerializer(many=True, read_only=True)
    center_name = serializers.CharField(source='center.name', read_only=True)

    class Meta:
        model = Image
        fields = ['id', 'file', 'taken_at', 'center', 'center_name', 'processed', 'detecciones']
