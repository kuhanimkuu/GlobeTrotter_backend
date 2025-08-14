from rest_framework import serializers
from .models import Payment

class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ("id", "booking", "gateway", "amount", "currency", "status", "txn_ref", "metadata", "created_at")
        read_only_fields = ("status", "txn_ref", "created_at")