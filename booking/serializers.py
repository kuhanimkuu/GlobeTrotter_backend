from rest_framework import serializers
from payments.models import RefundRequest 
from .models import Booking, BookingItem
from users.serializers import UserLiteSerializer
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from catalog.models import TourPackage  
from django.contrib.auth import get_user_model
from adapters.flights import ADAPTERS
from . import services
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
class PaymentSerializer(serializers.Serializer):
    payment_method = serializers.CharField(required=True)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=True)
    currency = serializers.CharField(default="USD")
    metadata = serializers.DictField(required=False)


class RefundRequestSerializer(serializers.ModelSerializer):
    requested_by = UserLiteSerializer(read_only=True)
    processed_by = UserLiteSerializer(read_only=True)

    class Meta:
        model = RefundRequest
        fields = (
            "id",
            "amount",
            "reason",
            "status",
            "requested_by",
            "processed_by",
            "created_at",
            "updated_at",
        )
class BookingReadSerializer(serializers.ModelSerializer):
    user = UserLiteSerializer(read_only=True)
    user_id = serializers.PrimaryKeyRelatedField(source="user", read_only=True)
    items = BookingItemReadSerializer(many=True, read_only=True)
    refund_requests = RefundRequestSerializer(many=True, read_only=True)  # ✅ include refunds
    booking_type = serializers.SerializerMethodField()
    external_service = serializers.CharField(read_only=True)
    external_reference = serializers.CharField(read_only=True)
    cancellation_reason = serializers.CharField(read_only=True)
    payment_status = serializers.SerializerMethodField()
    class Meta:
        model = Booking
        fields = (
            "id",
            "user",
            "user_id",
            "status",
            "total",
            "currency",
            "payment_status",
            "created_at",
            "items",
            "booking_type",
            "note",
            "external_service",
            "external_reference",
            "cancellation_reason",
            "refund_requests", 
        )
    def get_payment_status(self, obj):
   
        if hasattr(obj, "payment") and obj.payment:
            return obj.payment.status
        return None

    def get_booking_type(self, obj):
        if obj.package_id:
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
    payment = PaymentSerializer(required=False)
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

        payment_data = validated_data.pop("payment", None)
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
        from inventory.models import Car

        if detected_package:
            booking = services.create_tour_package_booking(
                user=user,
                tour_package_id=detected_package.id,
                start_date=validated_data.get("start_date"),
                guests=validated_data.get("guests", 1),
                currency=currency,
                note=note,
            )
        else:
            generic_items = []

            for item in parsed_items:
                obj = item["content_object"]
                unit_price = item["unit_price"]

                # ✅ Special handling for cars
                if isinstance(obj, Car):
                    start = item["start_date"]
                    end = item["end_date"]
                    duration = (end - start).days
                    unit_price = obj.daily_rate * duration

                generic_items.append({
                    "type": self._get_item_type(obj),
                    "id": obj.id,
                    "start_date": item["start_date"],
                    "end_date": item["end_date"],
                    "quantity": item["quantity"],
                    "unit_price": str(unit_price),
                })

            booking = services.create_generic_booking(
                user=user, items=generic_items, currency=currency, note=note
            )

        if payment_data:
            from payments.services import initiate_payment_for_booking
            try:
                payment = initiate_payment_for_booking(
                    booking=booking,
                    user=user,
                    payment_method=payment_data["payment_method"],
                    amount=payment_data["amount"],
                    currency=payment_data.get("currency", booking.currency),
                    metadata=payment_data.get("metadata", {}),
                )
                booking.payment_status = payment.status
                booking.save()
            except Exception as e:
                raise ValidationError({"payment": f"Payment failed: {str(e)}"})

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


from rest_framework import serializers
from rest_framework import serializers

class PassengerSerializer(serializers.Serializer):
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    email = serializers.EmailField(required=False, allow_blank=True)
    dob = serializers.DateField(required=False)    
    gender = serializers.ChoiceField(
        choices=["M", "F", "X"], required=False      
    )
    phone = serializers.CharField(required=False, allow_blank=True)

    def validate(self, data):
        
        if "email" in data and not data["email"].strip():
            raise serializers.ValidationError("Passenger email must not be empty if provided")
        return data

class ExternalFlightBookingSerializer(serializers.Serializer):
    provider = serializers.ChoiceField(choices=list(ADAPTERS.keys()))
    offer_id = serializers.CharField()
    passengers = PassengerSerializer(many=True, min_length=1)
    currency = serializers.CharField(default="USD", required=False)
    note = serializers.CharField(required=False, allow_blank=True)
    payment_token = serializers.CharField(required=False)
    payment = PaymentSerializer(required=False)

class HotelBookingSerializer(serializers.Serializer):
    room_type_id = serializers.IntegerField()
    check_in_date = serializers.DateField()
    check_out_date = serializers.DateField()
    rooms = serializers.IntegerField(min_value=1, default=1)
    currency = serializers.CharField(default="USD")
    note = serializers.CharField(required=False, allow_blank=True)
    payment = PaymentSerializer(required=False)
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
    payment = PaymentSerializer(required=False)

    def validate(self, data):
        start_date = data.get("start_date")
        end_date = data.get("end_date")

        if start_date and end_date and start_date >= end_date:
            raise ValidationError(_("end_date must be after start_date"))

        return data
