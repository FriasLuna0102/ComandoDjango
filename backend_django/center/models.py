from django.db import models

from backend_django.users.models import User


# Create your models here.
class Center(models.Model):
    name = models.CharField(max_length=100)
    address = models.TextField()
    users = models.ManyToManyField(User, related_name='centers')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Centro de Acopio'
        verbose_name_plural = 'Centros de Acopio'

    def __str__(self):
        return self.name

