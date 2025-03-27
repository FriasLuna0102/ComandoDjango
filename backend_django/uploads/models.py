from django.db import models
from django.utils import timezone

from backend_django.users.models import User
from center.models import Center
from core.models import TimeStampedModelMixin

# Create your models here.
class Image(TimeStampedModelMixin):
    file = models.FileField(upload_to='inventory_images/')
    taken_at = models.DateTimeField(default=timezone.now)
    taken_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    center = models.ForeignKey(Center, on_delete=models.CASCADE)
    processed = models.BooleanField(default=False)
    lighting_condition = models.CharField(max_length=50, blank=True)
    metadata = models.JSONField(default=dict)

    class Meta:
        verbose_name = 'Imagen'
        verbose_name_plural = 'Imagenes'

    def __str__(self):
        return self.file.name
