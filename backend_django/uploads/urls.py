from django.urls import path, include
from rest_framework.routers import DefaultRouter

from uploads.api.views import ImageViewSet, CenterViewSet

router = DefaultRouter()
router.register(r'centers', CenterViewSet)
router.register(r'images', ImageViewSet, basename='image')

urlpatterns = [
    path('', include(router.urls)),
]
