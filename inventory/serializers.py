from django.conf import settings
from rest_framework import serializers
from .models import Hotel, RoomType, Car, Flight
from catalog.models import Destination


class RoomHotelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Hotel
        fields = ("id", "name", "city", "country", "destination")


class RoomTypeSerializer(serializers.ModelSerializer):
    image = serializers.ImageField(required=False, allow_null=True, write_only=True)
    image_url = serializers.SerializerMethodField(read_only=True)
    hotel_id = serializers.PrimaryKeyRelatedField(
        queryset=Hotel.objects.all(),
        source="hotel",
        write_only=True
    )
    hotel = RoomHotelSerializer(read_only=True)

    class Meta:
        model = RoomType
        fields = (
            "id", "hotel", "hotel_id", "name", "capacity",
            "base_price", "currency", "quantity", "image", "image_url"
        )

    def get_image_url(self, obj):
        return obj.image.url if obj.image else None


class HotelSerializer(serializers.ModelSerializer):
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
        if not validated_data.get("destination"):
            validated_data["destination"] = validated_data.get("city", "Unknown")
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if not validated_data.get("destination"):
            validated_data["destination"] = validated_data.get("city", instance.city)
        return super().update(instance, validated_data)

    def get_cover_image_url(self, obj):
        if not obj.cover_image:
            return None
        if str(obj.cover_image).startswith("http"):
            return str(obj.cover_image)
        request = self.context.get("request")
        if request is not None:
            return request.build_absolute_uri(obj.cover_image.url)

        return obj.cover_image.url



class CarSerializer(serializers.ModelSerializer):
    available = serializers.BooleanField(default=True, required=False)
    carimage = serializers.ImageField(required=False, allow_null=True, write_only=True)
    image_url = serializers.SerializerMethodField(read_only=True)
    destination_id = serializers.PrimaryKeyRelatedField(
        queryset=Destination.objects.all(),
        source="destination",
        write_only=True,
        required=False, 
        allow_null=True
    )
    destination = serializers.SerializerMethodField(read_only=True)

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

    def get_destination(self, obj):
        from catalog.serializers import DestinationSerializer
        return DestinationSerializer(obj.destination).data if obj.destination else None
    def create(self, validated_data):
        print("DEBUG - validated_data before save:", validated_data)
        if "available" not in validated_data or validated_data["available"] is None:
            validated_data["available"] = True
        return super().create(validated_data)

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


class FlightSerializer(serializers.ModelSerializer):
    expired = serializers.SerializerMethodField()

    class Meta:
        model = Flight
        fields = (
            "id",
            "provider",
            "offer_id",
            "origin",
            "destination",
            "airline",
            "departure_time",
            "arrival_time",
            "seats_available",
            "departure_date",
            "return_date",
            "price",
            "currency",
            "expires_at",
            "created_at",
            "expired",
        )

    def get_expired(self, obj):
        return obj.is_expired()
