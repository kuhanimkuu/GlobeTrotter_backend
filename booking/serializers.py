from rest_framework import serializers
from .models import Booking, BookingItem
from users.serializers import UserLiteSerializer
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError

class BookingItemReadSerializer(serializers.ModelSerializer):
    # For read-only responses: show object representation minimally
    object_repr = serializers.SerializerMethodField()

    class Meta:
        model = BookingItem
        fields = ("id", "start_date", "end_date", "quantity", "unit_price", "line_total", "object_repr")

    def get_object_repr(self, obj):
        try:
            target = obj.content_object
            return str(target)
        except Exception:
            return None


class BookingReadSerializer(serializers.ModelSerializer):
    user = UserLiteSerializer(read_only=True)
    items = BookingItemReadSerializer(many=True, read_only=True)

    class Meta:
        model = Booking
        fields = ("id", "user", "status", "quantity", "total", "currency", "created_at", "items")



class BookingItemCreateSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=("package", "room", "car"))
    id = serializers.IntegerField()
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    quantity = serializers.IntegerField(min_value=1)


class BookingCreateSerializer(serializers.Serializer):
    event = serializers.IntegerField(required=False) 
    currency = serializers.CharField(default="USD")
    items = BookingItemCreateSerializer(many=True)

    def validate(self, attrs):
        items = attrs.get("items", [])
        if not items:
            raise serializers.ValidationError("At least one booking item is required.")
        return attrs

    def create(self, validated_data):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user is None or user.is_anonymous:
            raise ValidationError("Authentication required to create bookings.")

        items = validated_data["items"]
        currency = validated_data.get("currency", "USD")

       
        from . import services
        booking = services.create_booking(user=user, items=items, currency=currency)
        return booking

    def to_representation(self, instance):
        return BookingReadSerializer(instance, context=self.context).data