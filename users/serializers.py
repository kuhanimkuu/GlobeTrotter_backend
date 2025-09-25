from django.contrib.auth import get_user_model
from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password

User = get_user_model()

class UserLiteSerializer(serializers.ModelSerializer):
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "username", "first_name", "last_name", "avatar_url")

    def get_avatar_url(self, obj):
        avatar = getattr(obj, "avatar", None)
        if not avatar:
            return None
        try:
            return avatar.url
        except Exception:
            return None


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = (
            "id", "username", "email", "password", "password2",
            "first_name", "last_name", "phone", "company", "role"
        )

    def validate(self, attrs):
        if attrs.get("password") != attrs.get("password2"):
            raise serializers.ValidationError({"password": "Passwords must match."})
        if attrs.get("role") not in ["CUSTOMER", "AGENT", "ADMIN"]:
            raise serializers.ValidationError({"role": "Invalid role. Choose CUSTOMER or AGENT ."})

        return attrs

    def create(self, validated_data):
        validated_data.pop("password2", None)
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user

class UserDetailSerializer(serializers.ModelSerializer):
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "username", "email", "first_name", "last_name", "phone", "company", "role", "avatar_url")
        read_only_fields = ("role",)

    def get_avatar_url(self, obj):
        avatar = getattr(obj, "avatar", None)
        if not avatar:
            return None
        try:
            return avatar.url
        except Exception:
            return None