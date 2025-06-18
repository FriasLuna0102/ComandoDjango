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
        ('rf_detr','RF_DETR')
    ]
    tipo_modelo = models.CharField(max_length=20, choices=TIPO_MODELO_CHOICES)

    # Imagen original (opcional, si quieres guardarla)
    imagen = models.ImageField(upload_to='detecciones/', null=True, blank=True)

    # Resultados de la detección (guardados como JSON)
    resultados_json = models.TextField()

    # Metadatos adicionales
    numero_objetos = models.IntegerField(default=0)
    tiempo_procesamiento = models.FloatField(help_text="Tiempo de procesamiento en segundos", null=True, blank=True)

    # Campo para indicar si la detección ha sido confirmada por el usuario
    confirmed = models.BooleanField(default=False, help_text="Indica si el usuario ha confirmado los resultados")

    def set_resultados(self, resultados_dict):
        """Guarda los resultados como JSON"""
        self.resultados_json = json.dumps(resultados_dict)

        # Actualizar el número de objetos
        if 'detections' in resultados_dict:
            self.numero_objetos = len(resultados_dict.get('detections', []))
        elif 'count' in resultados_dict:
            # Usar el conteo directamente si está disponible
            self.numero_objetos = resultados_dict.get('count', 0)
        else:
            self.numero_objetos = 0

    def get_resultados(self):
        """Obtiene los resultados como diccionario"""
        try:
            return json.loads(self.resultados_json)
        except (json.JSONDecodeError, TypeError):
            return {}

    class Meta:
        verbose_name = "Detección"
        verbose_name_plural = "Detecciones"
        ordering = ['-fecha_creacion']

    def __str__(self):
        confirmation_status = "confirmada" if self.confirmed else "pendiente"
        return f"Detección {self.id} - {self.tipo_modelo} - {self.fecha_creacion} ({confirmation_status})"
