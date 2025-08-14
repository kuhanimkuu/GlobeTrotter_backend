from rest_framework import serializers
from .models import Review
from users.serializers import UserLiteSerializer

class ReviewSerializer(serializers.ModelSerializer):
    user = UserLiteSerializer(read_only=True)
    user_id = serializers.PrimaryKeyRelatedField(queryset=None, source="user", write_only=True)  # set in __init__ if needed

    class Meta:
        model = Review
        fields = ("id", "user", "user_id", "rating", "title", "body", "is_approved", "created_at")
        read_only_fields = ("is_approved", "created_at", "user")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
       
        from django.contrib.auth import get_user_model
        self.fields["user_id"].queryset = get_user_model().objects.all()

    def create(self, validated_data):
     
        return super().create(validated_data)