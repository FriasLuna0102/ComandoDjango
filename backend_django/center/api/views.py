from rest_framework import status, viewsets, generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken

from backend_django.users.api.serializers import UserSerializer
from center.api.serializer import CenterRegistrationSerializer, CenterSerializer
from center.models import Center


@api_view(['POST'])
@permission_classes([AllowAny])
def register_center(request):
    serializer = CenterRegistrationSerializer(data=request.data)
    if serializer.is_valid():
        data = serializer.save()
        user = data['user']

        # Generar token
        refresh = RefreshToken.for_user(user)

        return Response({
            'token': str(refresh.access_token),
            'user': UserSerializer(user).data,
            'center': CenterSerializer(data['center']).data
        }, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def login_user(request):
    email = request.data.get('email')
    password = request.data.get('password')

    if not email or not password:
        return Response({
            'error': 'Por favor proporcione email y contraseña'
        }, status=status.HTTP_400_BAD_REQUEST)

    user = authenticate(email=email, password=password)

    if user:
        refresh = RefreshToken.for_user(user)
        return Response({
            'token': str(refresh.access_token),
            'user': UserSerializer(user).data
        })

    return Response({
        'error': 'Credenciales inválidas'
    }, status=status.HTTP_401_UNAUTHORIZED)


class CenterViewSet(viewsets.ModelViewSet):
    queryset = Center.objects.all()
    serializer_class = CenterSerializer


class CenterUsersView(generics.ListAPIView):
    serializer_class = UserSerializer

    def get_queryset(self):
        center_id = self.kwargs['center_id']
        try:
            center = Center.objects.get(id=center_id)
            users = center.users.all()
            if not users.exists():
                raise NotFound(detail="No se encontraron usuarios para este centro de acopio.")
            return users
        except Center.DoesNotExist:
            raise NotFound(detail="Centro de acopio no encontrado.")

    def list(self, request, *args, **kwargs):
        try:
            queryset = self.get_queryset()
            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)
        except NotFound as e:
            return Response(
                {"error": str(e.detail)},
                status=status.HTTP_404_NOT_FOUND
            )

class ObtainAllCenters(generics.ListAPIView):
    serializer_class = CenterSerializer

    def get_queryset(self):
        queryset = Center.objects.all()
        if not queryset.exists():
            raise NotFound(detail="No se encontraron centros de acopio.")
        return queryset
