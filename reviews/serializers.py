from rest_framework import serializers
from .models import Review
from users.serializers import UserLiteSerializer
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType

User = get_user_model()


class ReviewSerializer(serializers.ModelSerializer):
    user = UserLiteSerializer(read_only=True)
    user_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source="user",
        write_only=True,
        required=False
    )
    content_type = serializers.CharField(write_only=True)
    object_id = serializers.IntegerField(write_only=True)
    content_object_display = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = (
            "id",
            "user",
            "user_id",
            "content_type",
            "object_id",
            "rating",
            "title",
            "body",
            "is_approved",
            "created_at",
            "content_object_display",
        )
        read_only_fields = ("is_approved", "created_at", "user")

    def create(self, validated_data):
        content_type_str = validated_data.pop("content_type")
        if "." not in content_type_str:
            raise serializers.ValidationError(
                {"content_type": "Must be in the format 'app_label.model' (e.g. 'inventory.hotel')."}
            )

        app_label, model = content_type_str.lower().split(".")
        try:
            ct = ContentType.objects.get(app_label=app_label, model=model)
        except ContentType.DoesNotExist:
            raise serializers.ValidationError(
                {"content_type": f"Invalid content type: {content_type_str}"}
            )

        validated_data["content_type"] = ct
        return super().create(validated_data)

    def get_content_object_display(self, obj):
        try:
            return str(obj.content_object)
        except Exception:
            return None
