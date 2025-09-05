from rest_framework import serializers
from .models import Destination, TourPackage, PackageImage


class PackageImageSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = PackageImage
        fields = ("id", "caption", "order", "image_url")

    def get_image_url(self, obj):
        img = getattr(obj, "image", None)
        return getattr(img, "url", None) if img else None


class DestinationSerializer(serializers.ModelSerializer):
    cover_image_url = serializers.SerializerMethodField()

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
            "cover_image_url",
        )
        read_only_fields = ("slug",)

    def get_cover_image_url(self, obj):
        img = getattr(obj, "cover_image", None)
        return getattr(img, "url", None) if img else None


class TourPackageSerializer(serializers.ModelSerializer):
    destination = DestinationSerializer(read_only=True)
    destination_id = serializers.PrimaryKeyRelatedField(
        queryset=Destination.objects.all(),
        source="destination",
        write_only=True
    )

    images = PackageImageSerializer(many=True, read_only=True)
    main_image_url = serializers.SerializerMethodField()

    class Meta:
        model = TourPackage
        fields = (
            "id",
            "title",
            "slug",
            "summary",
            "description",
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
            "images",
            "main_image_url",
        )
        read_only_fields = ("slug", "created_at", "updated_at")

    def get_main_image_url(self, obj):
        img = getattr(obj, "main_image", None)
        return getattr(img, "url", None) if img else None
