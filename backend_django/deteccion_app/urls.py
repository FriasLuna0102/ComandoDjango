from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DeteccionViewSet

router = DefaultRouter()
router.register(r'detecciones', DeteccionViewSet, basename='deteccion')

urlpatterns = [
    path('api/', include(router.urls)),
]
