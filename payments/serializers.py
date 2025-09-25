from rest_framework import serializers
from .models import Payment, RefundRequest
from booking.models import Booking
from booking.serializers import BookingReadSerializer


class PaymentSerializer(serializers.ModelSerializer):
    
    booking_id = serializers.PrimaryKeyRelatedField(
        queryset=Booking.objects.all(),
        source="booking",
        write_only=True
    )

   
    booking = BookingReadSerializer(read_only=True)

    class Meta:
        model = Payment
        fields = (
            "id",
            "booking",
            "booking_id",
            "gateway",
            "amount",
            "currency",
            "status",
            "txn_ref",
            "metadata",
            "created_at",
        )
        read_only_fields = ("status", "txn_ref", "created_at")


class RefundRequestSerializer(serializers.ModelSerializer):
    """Serializer for refund requests."""

 
    payment = serializers.PrimaryKeyRelatedField(read_only=True)
    requested_by = serializers.StringRelatedField(read_only=True)
    processed_by = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = RefundRequest
        fields = (
            "id",
            "payment",
            "requested_by",
            "status",
            "amount",
            "reason",
            "processed_by",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "status",
            "requested_by",
            "processed_by",
            "created_at",
            "updated_at",
        )