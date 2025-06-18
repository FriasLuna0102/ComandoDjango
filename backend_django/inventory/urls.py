from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .api.views import (
    ProductCategoryViewSet, InventorySnapshotViewSet,
    InventoryReportViewSet, AnalyticsReportViewSet
)

router = DefaultRouter()
router.register(r'categories', ProductCategoryViewSet, basename='category')
router.register(r'snapshots', InventorySnapshotViewSet, basename='snapshot')
router.register(r'reports', InventoryReportViewSet, basename='report')
router.register(r'analytics', AnalyticsReportViewSet, basename='analytics')

urlpatterns = [
    path('api/', include(router.urls)),
]
