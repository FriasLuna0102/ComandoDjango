from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework import status, generics, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.mixins import ListModelMixin
from rest_framework.mixins import RetrieveModelMixin
from rest_framework.mixins import UpdateModelMixin
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet

from center.models import Center

from .serializers import UserSerializer, UserSerializerForCenter, UserWithCentersSerializer

User = get_user_model()


class UserByEmailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, email):
        try:
            # Buscar usuario por email
            user = User.objects.get(email=email)

            # Verificar permisos (solo el propio usuario o un admin puede ver los datos)
            if request.user.is_superuser or request.user.email == email:
                serializer = UserWithCentersSerializer(user)  # Usar el nuevo serializer
                return Response(serializer.data)
            else:
                return Response(
                    {"error": "No tiene permisos para ver este usuario"},
                    status=status.HTTP_403_FORBIDDEN
                )
        except User.DoesNotExist:
            return Response(
                {"error": f"Usuario con email {email} no encontrado"},
                status=status.HTTP_404_NOT_FOUND
            )

# API para crear un nuevo usuario
class UserCreateView(generics.CreateAPIView):
    serializer_class = UserSerializer

    def create(self, request, *args, **kwargs):
        # Asegurarse de que center_id esté incluido en los datos
        data = request.data.copy()

        # Si no viene en la solicitud, intentar obtenerlo de la URL
        if 'center_id' not in data and 'center_id' in kwargs:
            data['center_id'] = kwargs.get('center_id')

        serializer = self.get_serializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {"message": "Usuario creado exitosamente", "data": serializer.data},
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# API para obtener, actualizar y eliminar usuario por ID
class UserDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    lookup_field = 'pk'

    def get_object(self):
        pk = self.kwargs.get('pk')
        try:
            return User.objects.get(pk=pk)
        except User.DoesNotExist:
            raise NotFound(detail="Usuario no encontrado.")

    def retrieve(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            return Response(serializer.data)
        except NotFound as e:
            return Response({"error": str(e.detail)}, status=status.HTTP_404_NOT_FOUND)

    def update(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            partial = kwargs.pop('partial', False)
            serializer = self.get_serializer(instance, data=request.data, partial=partial)

            if serializer.is_valid():
                # Si se incluye una nueva contraseña, establecerla correctamente
                if 'password' in request.data and request.data['password']:
                    instance.set_password(request.data['password'])
                    instance.save()

                self.perform_update(serializer)
                return Response(
                    {"message": "Usuario actualizado exitosamente", "data": serializer.data}
                )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except NotFound as e:
            return Response({"error": str(e.detail)}, status=status.HTTP_404_NOT_FOUND)

    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            self.perform_destroy(instance)
            return Response(
                {"message": "Usuario eliminado exitosamente"},
                status=status.HTTP_204_NO_CONTENT
            )
        except NotFound as e:
            return Response({"error": str(e.detail)}, status=status.HTTP_404_NOT_FOUND)


# API para asignar un usuario a un centro de acopio
class UserAssignToCenterView(generics.UpdateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializerForCenter

    def update(self, request, *args, **kwargs):
        user_id = kwargs.get('pk')
        center_id = request.data.get('center_id')

        if not center_id:
            return Response(
                {"error": "Se requiere el ID del centro de acopio"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response(
                {"error": "Usuario no encontrado"},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            from center.models import Center
            center = Center.objects.get(pk=center_id)
        except Center.DoesNotExist:
            return Response(
                {"error": "Centro de acopio no encontrado"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Añadir usuario al centro
        center.users.add(user)

        serializer = self.get_serializer(user)
        return Response({
            "message": f"Usuario asignado exitosamente al centro {center.name}",
            "data": serializer.data
        })


# API para eliminar un usuario de un centro de acopio
class UserRemoveFromCenterView(generics.UpdateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializerForCenter

    def update(self, request, *args, **kwargs):
        user_id = kwargs.get('pk')
        center_id = request.data.get('center_id')

        if not center_id:
            return Response(
                {"error": "Se requiere el ID del centro de acopio"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response(
                {"error": "Usuario no encontrado"},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            from center.models import Center
            center = Center.objects.get(pk=center_id)
        except Center.DoesNotExist:
            return Response(
                {"error": "Centro de acopio no encontrado"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Verificar si el usuario está en el centro
        if user not in center.users.all():
            return Response(
                {"error": "El usuario no pertenece a este centro de acopio"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Eliminar usuario del centro
        center.users.remove(user)

        serializer = self.get_serializer(user)
        return Response({
            "message": f"Usuario removido exitosamente del centro {center.name}",
            "data": serializer.data
        })


# URL para el ViewSet completo (CRUD) de usuarios
class UserViewSetComplete(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update({"request": self.request})
        return context

class UserViewSet(RetrieveModelMixin, ListModelMixin, UpdateModelMixin, GenericViewSet):
    serializer_class = UserSerializer
    queryset = User.objects.all()
    lookup_field = "pk"

    def get_queryset(self, *args, **kwargs):
        assert isinstance(self.request.user.id, int)
        return self.queryset.filter(id=self.request.user.id)

    @action(detail=False)
    def me(self, request):
        serializer = UserSerializer(request.user, context={"request": request})
        return Response(status=status.HTTP_200_OK, data=serializer.data)


class UserSearchView(generics.ListAPIView):
    serializer_class = UserSerializer

    def get_queryset(self):
        queryset = User.objects.all()

        # Filtrar por ID de usuario
        user_id = self.request.query_params.get('id', None)
        if user_id:
            queryset = queryset.filter(id=user_id)

        # Filtrar por nombre o apellido (búsqueda parcial)
        name = self.request.query_params.get('name', None)
        if name:
            queryset = queryset.filter(
                Q(first_name__icontains=name) |
                Q(last_name__icontains=name) |
                Q(username__icontains=name)
            )

        # Filtrar por ID del centro de acopio
        center_id = self.request.query_params.get('center_id', None)
        if center_id:
            try:
                center = Center.objects.get(id=center_id)
                queryset = queryset.filter(centers=center)
            except Center.DoesNotExist:
                raise NotFound(detail="Centro de acopio no encontrado.")

        # Filtrar por nombre del centro de acopio
        center_name = self.request.query_params.get('center_name', None)
        if center_name:
            centers = Center.objects.filter(name__icontains=center_name)
            if not centers.exists():
                raise NotFound(detail="No se encontraron centros de acopio con ese nombre.")
            queryset = queryset.filter(centers__in=centers).distinct()

        if not queryset.exists():
            raise NotFound(detail="No se encontraron usuarios con los criterios especificados.")

        return queryset

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
