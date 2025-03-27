from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .api import views
from .api.views import CenterViewSet, ObtainAllCenters

router = DefaultRouter()
router.register(r'centers', CenterViewSet)

urlpatterns = [

    path('', include(router.urls)),
    path('all-centers/', ObtainAllCenters.as_view(), name='all-centers'),

    path('register/', views.register_center, name='register_center'),
    path('login/', views.login_user, name='login_user'),
]
