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
        required=False  # because we auto-assign in perform_create
    )

    # Expose GenericForeignKey as friendly fields
    content_type = serializers.CharField(write_only=True)
    object_id = serializers.IntegerField(write_only=True)

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
        )
        read_only_fields = ("is_approved", "created_at", "user")

    def create(self, validated_data):
        # Convert content_type string to ContentType instance
        content_type_str = validated_data.pop("content_type")
        try:
            ct = ContentType.objects.get(model=content_type_str.lower())
        except ContentType.DoesNotExist:
            raise serializers.ValidationError(
                {"content_type": f"Invalid content type: {content_type_str}"}
            )

        validated_data["content_type"] = ct
        return super().create(validated_data)
