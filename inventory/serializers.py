from rest_framework import serializers
from .models import Hotel, RoomType, Car, Flight
from catalog.models import Destination
from catalog.serializers import DestinationSerializer


class RoomHotelSerializer(serializers.ModelSerializer):
    """
    Nested serializer for hotel details inside RoomType
    """
    class Meta:
        model = Hotel
        fields = ("id", "name", "city", "country", "destination")


class RoomTypeSerializer(serializers.ModelSerializer):
    """
    Serializer for RoomType including optional image upload
    """
    image = serializers.ImageField(required=False, allow_null=True, write_only=True)
    image_url = serializers.SerializerMethodField(read_only=True)
    hotel_id = serializers.PrimaryKeyRelatedField(
        queryset=Hotel.objects.all(),
        source="hotel",
        write_only=True
    )
    hotel = RoomHotelSerializer(read_only=True)  # nested hotel info

    class Meta:
        model = RoomType
        fields = (
            "id", "hotel", "hotel_id", "name", "capacity",
            "base_price", "currency", "quantity", "image", "image_url"
        )

    def get_image_url(self, obj):
        return obj.image.url if obj.image else None


class HotelSerializer(serializers.ModelSerializer):
    """
    Serializer for Hotel with optional destination and cover image
    """
    destination = serializers.CharField(required=False, allow_blank=True)
    cover_image = serializers.ImageField(required=False, allow_null=True, write_only=True)
    cover_image_url = serializers.SerializerMethodField(read_only=True)
    room_types = RoomTypeSerializer(many=True, read_only=True)
    description = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = Hotel
        fields = (
            "id", "name", "address", "city", "country", "destination",
            "rating", "is_active", "description",
            "cover_image", "cover_image_url", "room_types"
        )

    def create(self, validated_data):
        # Default destination to city if not provided
        if not validated_data.get("destination"):
            validated_data["destination"] = validated_data.get("city", "Unknown")
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if not validated_data.get("destination"):
            validated_data["destination"] = validated_data.get("city", instance.city)
        return super().update(instance, validated_data)

    def get_cover_image_url(self, obj):
        return obj.cover_image.url if obj.cover_image else None


class CarSerializer(serializers.ModelSerializer):
    """
    Serializer for Car with optional image
    """
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
            "carimage", "image_url", "destination", "destination_id",
            "driver_name", "driver_contact"
        )

    def get_image_url(self, obj):
        return obj.carimage.url if obj.carimage else None


class DestinationCarsSerializer(serializers.ModelSerializer):
    """
    Serializer for Destination including its cars
    """
    cars = CarSerializer(many=True, read_only=True)

    class Meta:
        model = Destination
        fields = ("id", "name", "country", "cars")


class DestinationHotelsSerializer(serializers.ModelSerializer):
    """
    Serializer for Destination including its hotels
    """
    hotels = HotelSerializer(many=True, read_only=True)

    class Meta:
        model = Destination
        fields = ("id", "name", "country", "hotels")
class FlightSerializer(serializers.ModelSerializer):
    class Meta:
        model = Flight
        fields = (
            "id", "provider", "offer_id",
            "origin", "destination",
            "departure_time", "arrival_time",
            "airline", "price", "currency", "seats_available"
        )
