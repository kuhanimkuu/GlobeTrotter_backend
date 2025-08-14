from rest_framework import serializers
from .models import Hotel, RoomType, Car
from catalog.serializers import DestinationSerializer

class RoomTypeSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = RoomType
        fields = ("id", "hotel", "name", "capacity", "base_price", "currency", "quantity", "image_url")
        read_only_fields = ("hotel",)

    def get_image_url(self, obj):
        img = getattr(obj, "image", None)
        return getattr(img, "url", None) if img else None


class HotelSerializer(serializers.ModelSerializer):
    destination = DestinationSerializer(read_only=True)
    destination_id = serializers.PrimaryKeyRelatedField(queryset=None, source="destination", write_only=True)  # set queryset in __init__
    cover_image_url = serializers.SerializerMethodField()
    room_types = RoomTypeSerializer(many=True, read_only=True)

    class Meta:
        model = Hotel
        fields = ("id", "name", "destination", "destination_id", "address", "rating", "is_active", "cover_image_url", "room_types")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # avoid import-time circular import
        from catalog.models import Destination
        self.fields["destination_id"].queryset = Destination.objects.all()

    def get_cover_image_url(self, obj):
        img = getattr(obj, "cover_image", None)
        return getattr(img, "url", None) if img else None


class CarSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Car
        fields = ("id", "provider", "make", "model", "category", "daily_rate", "currency", "available", "image_url")

    def get_image_url(self, obj):
        img = getattr(obj, "carimage", None)
        return getattr(img, "url", None) if img else None