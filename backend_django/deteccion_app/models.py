from django.db import models
import uuid
import json
from center.models import Center
from uploads.models import Image

class Deteccion(models.Model):
    """Modelo para almacenar los resultados de las detecciones"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    center = models.ForeignKey(Center, on_delete=models.CASCADE, related_name='detecciones', null=True)
    image = models.ForeignKey(Image, on_delete=models.SET_NULL, related_name='detecciones', null=True)



    # Tipo de modelo utilizado
    TIPO_MODELO_CHOICES = [
        ('yolo', 'YOLO'),
        ('cl', 'YOLO 2.0'),
    ]
    tipo_modelo = models.CharField(max_length=20, choices=TIPO_MODELO_CHOICES)

    # Imagen original (opcional, si quieres guardarla)
    imagen = models.ImageField(upload_to='detecciones/', null=True, blank=True)

    # Resultados de la detección (guardados como JSON)
    resultados_json = models.TextField()

    # Metadatos adicionales
    numero_objetos = models.IntegerField(default=0)
    tiempo_procesamiento = models.FloatField(help_text="Tiempo de procesamiento en segundos", null=True, blank=True)

    def set_resultados(self, resultados_dict):
        """Guarda los resultados como JSON"""
        self.resultados_json = json.dumps(resultados_dict)
        self.numero_objetos = len(resultados_dict.get('detections', []))


    def get_resultados(self):
        """Obtiene los resultados como diccionario"""
        return json.loads(self.resultados_json)



    class Meta:
        verbose_name = "Detección"
        verbose_name_plural = "Detecciones"
        ordering = ['-fecha_creacion']

    def __str__(self):
        return f"Detección {self.id} - {self.tipo_modelo} - {self.fecha_creacion}"
