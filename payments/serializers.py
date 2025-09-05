from rest_framework import serializers
from .models import Payment
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
