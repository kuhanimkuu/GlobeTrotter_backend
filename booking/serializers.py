from rest_framework import serializers
from .models import Booking, BookingItem
from users.serializers import UserLiteSerializer
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from catalog.models import TourPackage  
from django.contrib.auth import get_user_model

User = get_user_model()


class BookingItemReadSerializer(serializers.ModelSerializer):
    object_repr = serializers.SerializerMethodField()
    object_id = serializers.IntegerField(read_only=True)
    content_type = serializers.CharField(source="content_type.model", read_only=True)
    item_type = serializers.SerializerMethodField()

    class Meta:
        model = BookingItem
        fields = (
            "id",
            "start_date",
            "end_date",
            "quantity",
            "unit_price",
            "line_total",
            "object_repr",
            "object_id",
            "content_type",
            "item_type",
        )

    def get_object_repr(self, obj):
        try:
            return str(obj.content_object)
        except Exception:
            return None

    def get_item_type(self, obj):
        """Return the item type based on content_type"""
        content_type = obj.content_type
        if content_type:
            type_map = {
                'tourpackage': 'package',
                'hotel': 'hotel',
                'roomtype': 'room',
                'car': 'car',
            }
            return type_map.get(content_type.model, content_type.model)
        return None


class BookingReadSerializer(serializers.ModelSerializer):
    user = UserLiteSerializer(read_only=True)
    user_id = serializers.PrimaryKeyRelatedField(source="user", read_only=True)
    items = BookingItemReadSerializer(many=True, read_only=True)
    booking_type = serializers.SerializerMethodField()
    external_service = serializers.CharField(read_only=True)
    external_reference = serializers.CharField(read_only=True)
    cancellation_reason = serializers.CharField(read_only=True)  # ✅ NEW: match updated model

    class Meta:
        model = Booking
        fields = (
            "id",
            "user",
            "user_id",
            "status",
            "total",
            "currency",
            "created_at",
            "items",
            "booking_type",
            "note",
            "external_service",
            "external_reference",
            "cancellation_reason",   # ✅ included
        )

    def get_booking_type(self, obj):
        """Determine booking type"""
        if obj.package_id:  # ✅ nullable-safe check
            return "package"
        if obj.external_service:
            return "flight"

        if obj.items.exists():
            item_types = set(
                item.content_type.model for item in obj.items.all() if item.content_type
            )
            if len(item_types) == 1:
                return list(item_types)[0]
            return "mixed"

        return "unknown"


class BookingItemCreateSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=("package", "hotel", "room", "car"))
    id = serializers.IntegerField()
    start_date = serializers.DateField(required=False, allow_null=True)
    end_date = serializers.DateField(required=False, allow_null=True)
    quantity = serializers.IntegerField(min_value=1, default=1)
    unit_price = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)

    def validate(self, data):
        sd = data.get("start_date")
        ed = data.get("end_date")
        item_type = data.get("type")

        if item_type in ["hotel", "room", "car"]:
            if not sd or not ed:
                raise ValidationError(_(f"start_date and end_date are required for {item_type} bookings."))
            if sd > ed:
                raise ValidationError(_("start_date must be before end_date"))

        return data


class BookingCreateSerializer(serializers.Serializer):
    currency = serializers.CharField(default="USD")
    items = BookingItemCreateSerializer(many=True)
    note = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        items = attrs.get("items", [])
        if not items:
            raise serializers.ValidationError(_("At least one booking item is required."))

        item_types = [item.get("type") for item in items]
        if "package" in item_types and len(item_types) > 1:
            raise serializers.ValidationError(_("Cannot mix tour packages with individual services in one booking."))

        return attrs

    def _resolve_item_object(self, item):
        t = item.get("type")
        obj_id = item.get("id")
        start_date = item.get("start_date")
        end_date = item.get("end_date")
        quantity = item.get("quantity", 1)
        unit_price = item.get("unit_price")

        TYPE_TO_MODEL = {
            "package": ("catalog", "tourpackage"),
            "hotel": ("inventory", "hotel"),
            "room": ("inventory", "roomtype"),
            "car": ("inventory", "car"),
        }

        if t not in TYPE_TO_MODEL:
            raise ValidationError(_(f"Unknown item type '{t}'"))

        app_label, model_name = TYPE_TO_MODEL[t]
        try:
            ct = ContentType.objects.get(app_label=app_label, model=model_name)
        except ContentType.DoesNotExist:
            raise ValidationError(_(f"Content type for {app_label}.{model_name} not found."))

        model_cls = ct.model_class()
        if model_cls is None:
            raise ValidationError(_(f"Model class for {app_label}.{model_name} could not be loaded."))

        try:
            obj = model_cls.objects.get(pk=obj_id)
        except model_cls.DoesNotExist:
            raise ValidationError(_(f"{model_name} with id {obj_id} not found."))

        if t != "package":
            if hasattr(obj, 'available') and not obj.available:
                raise ValidationError(_(f"{model_name} with id {obj_id} is not available."))
            if hasattr(obj, 'is_active') and not obj.is_active:
                raise ValidationError(_(f"{model_name} with id {obj_id} is not active."))

        return {
            "content_object": obj,
            "start_date": start_date,
            "end_date": end_date,
            "quantity": quantity,
            "unit_price": unit_price,
        }

    def create(self, validated_data):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user is None or user.is_anonymous:
            raise ValidationError(_("Authentication required to create bookings."))

        items_data = validated_data["items"]
        currency = validated_data.get("currency", "USD")
        note = validated_data.get("note", "")

        parsed_items = []
        detected_package = None

        for it in items_data:
            parsed = self._resolve_item_object(it)
            parsed_items.append(parsed)
            if isinstance(parsed["content_object"], TourPackage) and detected_package is None:
                detected_package = parsed["content_object"]

        from . import services

        if detected_package:
            booking = services.create_tour_package_booking(
                user=user,
                package=detected_package,
                items=parsed_items,
                currency=currency,
                note=note
            )
        else:
            generic_items = []
            for item in parsed_items:
                generic_items.append({
                    "type": self._get_item_type(item["content_object"]),
                    "id": item["content_object"].id,
                    "start_date": item["start_date"],
                    "end_date": item["end_date"],
                    "quantity": item["quantity"],
                    "unit_price": str(item["unit_price"]) if item["unit_price"] else None,
                })

            booking = services.create_generic_booking(
                user=user,
                items=generic_items,
                currency=currency,
                note=note
            )

        return booking

    def _get_item_type(self, content_object):
        type_map = {
            'TourPackage': 'package',
            'Hotel': 'hotel',
            'RoomType': 'room',
            'Car': 'car',
        }
        return type_map.get(content_object.__class__.__name__, 'unknown')

    def to_representation(self, instance):
        return BookingReadSerializer(instance, context=self.context).data


class ExternalFlightBookingSerializer(serializers.Serializer):
    provider = serializers.ChoiceField(choices=['amadeus', 'duffel'])
    offer_id = serializers.CharField()
    passengers = serializers.ListField(
        child=serializers.DictField(),
        min_length=1
    )
    currency = serializers.CharField(default="USD")
    note = serializers.CharField(required=False, allow_blank=True)
    payment_token = serializers.CharField(required=False)

    def validate_passengers(self, value):
        for passenger in value:
            if not passenger.get('first_name') or not passenger.get('last_name'):
                raise ValidationError("Each passenger must have first_name and last_name")
        return value


class HotelBookingSerializer(serializers.Serializer):
    room_type_id = serializers.IntegerField()
    check_in_date = serializers.DateField()
    check_out_date = serializers.DateField()
    rooms = serializers.IntegerField(min_value=1, default=1)
    currency = serializers.CharField(default="USD")
    note = serializers.CharField(required=False, allow_blank=True)

    def validate(self, data):
        check_in = data.get("check_in_date")
        check_out = data.get("check_out_date")

        if check_in and check_out and check_in >= check_out:
            raise ValidationError(_("check_out_date must be after check_in_date"))

        return data


class CarBookingSerializer(serializers.Serializer):
    car_id = serializers.IntegerField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    currency = serializers.CharField(default="USD")
    note = serializers.CharField(required=False, allow_blank=True)

    def validate(self, data):
        start_date = data.get("start_date")
        end_date = data.get("end_date")

        if start_date and end_date and start_date >= end_date:
            raise ValidationError(_("end_date must be after start_date"))

        return data
