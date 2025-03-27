from rest_framework import serializers, viewsets
from django.contrib.auth import get_user_model

from backend_django.users.api.serializers import UserSerializer
from center.models import Center

User = get_user_model()


class CenterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Center
        fields = ('id', 'name', 'address', 'created_at')
        read_only_fields = ('created_at',)


class CenterRegistrationSerializer(serializers.Serializer):
    center = CenterSerializer()
    user = UserSerializer()

    def create(self, validated_data):
        user_data = validated_data.pop('user')
        center_data = validated_data.pop('center')

        # Crear usuario
        user = UserSerializer().create(user_data)

        # Crear centro y asociar usuario
        center = Center.objects.create(
            name=center_data['name'],
            address=center_data['address']
        )
        center.users.add(user)
        center.save()

        return {
            'user': user,
            'center': center,
        }

class CenterViewSet(viewsets.ModelViewSet):
    queryset = Center.objects.all()
    serializer_class = CenterSerializer
