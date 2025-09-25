from rest_framework import serializers
from reviews.models import Review
from .models import Destination, TourPackage, PackageImage
from inventory.serializers import HotelSerializer, CarSerializer
from inventory.models import Hotel, Car
from django.utils import timezone
from django.db.models import Avg
from django.contrib.contenttypes.models import ContentType

class PackageImageSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = PackageImage
        fields = ("id", "caption", "order", "image_url")

    def get_image_url(self, obj):
        img = getattr(obj, "image", None)
        return getattr(img, "url", None) if img else None


class DestinationSerializer(serializers.ModelSerializer):
    cover_image = serializers.ImageField(required=False, allow_null=True, write_only=True)
    cover_image_url = serializers.SerializerMethodField(read_only=True)
    class Meta:
        model = Destination
        fields = (
            "id",
            "name",
            "country",
            "city",
            "short_description",
            "description",
            "latitude",
            "longitude",
            "slug",
            "cover_image",
            "cover_image_url",
        )
        read_only_fields = ("slug",)

    def get_cover_image_url(self, obj):
        img = getattr(obj, "cover_image", None)
        return getattr(img, "url", None) if img else None


class TourPackageSerializer(serializers.ModelSerializer):
    average_rating = serializers.SerializerMethodField()
    total_reviews = serializers.SerializerMethodField()
    destination = DestinationSerializer(read_only=True)
    destination_id = serializers.PrimaryKeyRelatedField(
        queryset=Destination.objects.all(),
        source="destination",
        write_only=True
    )
    hotel = HotelSerializer(read_only=True)
    hotel_id = serializers.PrimaryKeyRelatedField(
        queryset=Hotel.objects.all(),
        source="hotel",
        write_only=True,
        required=False,
        allow_null=True
    )
    car = CarSerializer(read_only=True)
    car_id = serializers.PrimaryKeyRelatedField(
        queryset=Car.objects.all(),
        source="car",
        write_only=True,
        required=False,
        allow_null=True
    )
    images = PackageImageSerializer(many=True, read_only=True)

    main_image_url = serializers.SerializerMethodField()
    total_price = serializers.SerializerMethodField()
    is_expired = serializers.SerializerMethodField()
    total_bookings = serializers.SerializerMethodField()
    total_commission_earned = serializers.SerializerMethodField()
    reviews = serializers.SerializerMethodField()

    class Meta:
        model = TourPackage
        fields = (
            "id",
            "title",
            "slug",
            "summary",
            "description",
            "highlights",
            "policies",
            "start_date",
            "end_date",
            "duration_days",
            "base_price",
            "currency",
            "inclusions",
            "exclusions",
            "max_capacity",
            "is_active",
            "created_at",
            "updated_at",
            "destination",
            "destination_id",
            "organizer",
            "hotel",
            "hotel_id",
            "car",
            "car_id",
            "commission",
            "nights",
            "car_days",
            "main_image",
            "images",
            "main_image_url",
            "total_price",
            "is_expired",
            "total_bookings",
            "total_commission_earned",
            "reviews",
            "average_rating",
            "total_reviews",
        )
        read_only_fields = (
            "slug",
            "created_at",
            "updated_at",
            "total_price",
            "main_image_url",
            "is_expired",
            "total_bookings",
            "total_commission_earned",
            "reviews",
        )

    def get_main_image_url(self, obj):
        return getattr(obj.main_image, "url", None) if obj.main_image else None

    def get_total_price(self, obj):
        if obj.hotel and hasattr(obj.hotel, "room_types") and obj.hotel.room_types.exists():
            hotel_price = obj.hotel.room_types.first().base_price * obj.nights
        else:
            hotel_price = 0

        car_price = (getattr(obj.car, "daily_rate", 0) or 0) * obj.car_days
        subtotal = obj.base_price + hotel_price + car_price
        commission_amount = (subtotal * obj.commission) / 100
        return subtotal + commission_amount

    def get_is_expired(self, obj):
        if not obj.end_date:
            return False
        end_date = obj.end_date.date() if hasattr(obj.end_date, "date") else obj.end_date
        return end_date < timezone.now().date()

    def get_total_bookings(self, obj):
        return obj.bookings.filter(status="CONFIRMED").count() if hasattr(obj, "bookings") else 0

    def get_total_commission_earned(self, obj):
        if hasattr(obj, "bookings"):
            confirmed_bookings = obj.bookings.filter(status="CONFIRMED")
            total_sales = sum(b.total for b in confirmed_bookings)
            return (total_sales * obj.commission) / 100
        return 0

    def get_reviews(self, obj):
        content_type = ContentType.objects.get_for_model(TourPackage)
        reviews_qs = Review.objects.filter(
        content_type=content_type, object_id=obj.id, is_approved=True
    )
        return [
        {
            "user": review.user.username,
            "rating": review.rating,
            "comment": review.comment,
            "created_at": review.created_at,
        }
        for review in reviews_qs
    ]
    def get_average_rating(self, obj):
        content_type = ContentType.objects.get_for_model(TourPackage)
        return Review.objects.filter(
        content_type=content_type, object_id=obj.id, is_approved=True
    ).aggregate(Avg('rating'))['rating__avg'] or 0

    def get_total_reviews(self, obj):
        content_type = ContentType.objects.get_for_model(TourPackage)
        return Review.objects.filter(
        content_type=content_type, object_id=obj.id, is_approved=True
    ).count()