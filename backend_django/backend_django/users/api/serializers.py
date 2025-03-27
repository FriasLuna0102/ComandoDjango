from rest_framework import serializers
from django.contrib.auth import get_user_model

from center.models import Center

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    center_id = serializers.IntegerField(write_only=True, required=False)

    class Meta:
        model = User
        fields = ('id', 'email', 'name', 'password', 'is_superuser', 'is_staff', 'center_id')
        extra_kwargs = {
            'password': {'write_only': True},
            'id': {'read_only': True}
        }

    def create(self, validated_data):
        password = validated_data.pop('password')
        center_id = validated_data.pop('center_id', None)

        user = User(**validated_data)
        user.set_password(password)
        user.save()

        # Asignar al centro si se proporcionó un ID
        if center_id:
            try:
                center = Center.objects.get(id=center_id)
                center.users.add(user)
            except Center.DoesNotExist:
                # Manejar el error, pero no fallar la creación del usuario
                pass

        return user

class UserSerializerForCenter(serializers.ModelSerializer):
    centers = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'centers']

    def get_centers(self, obj):
        return [
            {
                'id': center.id,
                'name': center.name
            }
            for center in obj.centers.all()
        ]


class UserWithCentersSerializer(serializers.ModelSerializer):
    centers = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'email', 'name', 'is_superuser', 'is_staff', 'centers']

    def get_centers(self, obj):
        return [
            {
                'id': center.id,
                'name': center.name,
                'address': center.address
            }
            for center in obj.centers.all()
        ]
