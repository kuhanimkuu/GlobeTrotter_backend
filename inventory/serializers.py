from rest_framework import serializers
from .models import Hotel, RoomType, Car
from catalog.serializers import DestinationSerializer
from catalog.models import Destination


class RoomHotelSerializer(serializers.ModelSerializer):
    destination = DestinationSerializer(read_only=True)

    class Meta:
        model = Hotel
        fields = ("id", "name", "destination")


class RoomTypeSerializer(serializers.ModelSerializer):
    image = serializers.ImageField(required=False, allow_null=True, write_only=True)
    image_url = serializers.SerializerMethodField(read_only=True)
    hotel_id = serializers.PrimaryKeyRelatedField(
        queryset=Hotel.objects.all(),
        source="hotel",
        write_only=True
    )
    hotel = RoomHotelSerializer(read_only=True)  # nested hotel details

    class Meta:
        model = RoomType
        fields = (
            "id", "hotel", "hotel_id", "name", "capacity",
            "base_price", "currency", "quantity", "image", "image_url"
        )

    def get_image_url(self, obj):
        img = getattr(obj, "image", None)
        return getattr(img, "url", None) if img else None


class HotelSerializer(serializers.ModelSerializer):
    destination = DestinationSerializer(read_only=True)
    destination_id = serializers.PrimaryKeyRelatedField(
        queryset=Destination.objects.all(),
        source="destination",
        write_only=True
    )
    cover_image = serializers.ImageField(required=False, allow_null=True, write_only=True)
    cover_image_url = serializers.SerializerMethodField(read_only=True)
    room_types = RoomTypeSerializer(many=True, read_only=True)

    class Meta:
        model = Hotel
        fields = (
            "id", "name", "destination", "destination_id", "address",
            "rating", "is_active", "cover_image", "cover_image_url", "room_types"
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["destination_id"].queryset = Destination.objects.all()

    def get_cover_image_url(self, obj):
        img = getattr(obj, "cover_image", None)
        return getattr(img, "url", None) if img else None


class CarSerializer(serializers.ModelSerializer):
    carimage = serializers.ImageField(required=False, allow_null=True, write_only=True)
    image_url = serializers.SerializerMethodField(read_only=True)
    destination_id = serializers.PrimaryKeyRelatedField(
        queryset=Destination.objects.all(),
        source="destination",
        write_only=True
    )
    destination = DestinationSerializer(read_only=True)

    class Meta:
        model = Car
        fields = (
            "id", "provider", "make", "model", "category",
            "daily_rate", "currency", "available",
            "carimage", "image_url", "destination", "destination_id"
        )

    def get_image_url(self, obj):
        if obj.carimage:
            return obj.carimage.url
        return None
    
class DestinationCarsSerializer(serializers.ModelSerializer):
    cars = CarSerializer(many=True, read_only=True)

    class Meta:
        model = Destination
        fields = ("id", "name", "country", "cars")


class DestinationHotelsSerializer(serializers.ModelSerializer):
    hotels = HotelSerializer(many=True, read_only=True)

    class Meta:
        model = Destination
        fields = ("id", "name", "country", "hotels")