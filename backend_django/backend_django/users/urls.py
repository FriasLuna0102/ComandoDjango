from django.urls import path, include
from rest_framework.routers import DefaultRouter

from center.api.views import CenterViewSet, CenterUsersView
from .api.views import (
    UserSearchView, UserCreateView, UserDetailView,
    UserAssignToCenterView, UserRemoveFromCenterView, UserByEmailView
)
from .views import user_detail_view
from .views import user_redirect_view
from .views import user_update_view

app_name = "users"

# Router para centros de acopio
center_router = DefaultRouter()
center_router.register(r'centers', CenterViewSet)

# Router para usuarios (opcional si quieres usar el ViewSet completo)
# user_router = DefaultRouter()
# user_router.register(r'api/users', UserViewSetComplete)

urlpatterns = [
    # URLs de la interfaz web existentes
    path("~redirect/", view=user_redirect_view, name="redirect"),
    path("~update/", view=user_update_view, name="update"),
    path("<int:pk>/", view=user_detail_view, name="detail"),

    # Incluir rutas del router de centros
    path('api/', include(center_router.urls)),

    # API de usuarios en centros
    path('api/centers/<int:center_id>/users/', CenterUsersView.as_view(), name='center-users'),

    # APIs de usuario
    path('api/users/search/', UserSearchView.as_view(), name='user-search'),
    path('api/users/create/', UserCreateView.as_view(), name='user-create'),
    path('api/users/<int:pk>/', UserDetailView.as_view(), name='user-detail'),
    path('api/users/<int:pk>/assign-center/', UserAssignToCenterView.as_view(), name='user-assign-center'),
    path('api/users/<int:pk>/remove-center/', UserRemoveFromCenterView.as_view(), name='user-remove-center'),
    path('api/users/by-email/<str:email>/', UserByEmailView.as_view(), name='user-by-email'),
    # Incluir router de usuarios (descomentar si quieres usar el ViewSet completo)
    # path('api/', include(user_router.urls)),
]
