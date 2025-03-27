from django.contrib import admin

from deteccion_app.models import Deteccion


# Register your models here.
@admin.register(Deteccion)
class DeteccionAdmin(admin.ModelAdmin):
    list_display = ('id', 'fecha_creacion', 'tipo_modelo', 'numero_objetos')
    search_fields = ('id', 'fecha_creacion', 'tipo_modelo', 'numero_objetos')
    list_filter = ('tipo_modelo',)
    ordering = ('-fecha_creacion',)
    readonly_fields = ('id', 'fecha_creacion', 'tipo_modelo', 'numero_objetos', 'tiempo_procesamiento')

