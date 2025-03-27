from django.contrib import admin

from uploads.models import Image


# Register your models here.
@admin.register(Image)
class ImageAdmin(admin.ModelAdmin):
    list_display = ('file', 'taken_at', 'taken_by', 'center', 'processed', 'lighting_condition', 'metadata')
    search_fields = ('file', 'taken_at', 'lighting_condition', 'metadata')
    list_filter = ('taken_at', 'taken_by', 'center', 'processed', 'lighting_condition')
    ordering = ('-taken_at',)
