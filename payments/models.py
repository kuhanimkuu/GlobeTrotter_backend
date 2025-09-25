from django.db import models
from decimal import Decimal
from django.conf import settings
class Payment(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        SUCCESS = "SUCCESS", "Success"
        FAILED = "FAILED", "Failed"
        REFUNDED = "REFUNDED", "Refunded"

    booking = models.ForeignKey("booking.Booking", on_delete=models.CASCADE, related_name="payments")
    gateway = models.CharField(max_length=50) 
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    currency = models.CharField(max_length=3, default="USD")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    txn_ref = models.CharField(max_length=255, blank=True, null=True, help_text="Gateway transaction reference")
    idempotency_key = models.CharField(max_length=255, blank=True, null=True)
    metadata = models.JSONField(default=dict, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["booking","status","created_at"]),
            models.Index(fields=["gateway","txn_ref"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["gateway", "txn_ref"], name="uq_gateway_txn_ref", deferrable=models.Deferrable.DEFERRED)
        ]

    def __str__(self): return f"{self.gateway}:{self.pk} → {self.booking_id} [{self.status}]"

    @property
    def is_terminal(self) -> bool:
        return self.status in {self.Status.SUCCESS, self.Status.FAILED, self.Status.REFUNDED}
class RefundRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        COMPLETED = "COMPLETED", "Completed"

    payment = models.ForeignKey("payments.Payment", on_delete=models.CASCADE, related_name="refund_requests")
    requested_by = models.ForeignKey(
    settings.AUTH_USER_MODEL,
    on_delete=models.CASCADE,
    related_name="refund_requests",
)
    booking = models.ForeignKey("booking.Booking", on_delete=models.CASCADE, related_name="refund_requests", null=True,blank=True)  
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    reason = models.TextField(blank=True, null=True)
    processed_by = models.ForeignKey(
    settings.AUTH_USER_MODEL,
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    related_name="processed_refunds",
)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["payment", "status"]),
        ]

    def __str__(self):
        return f"RefundRequest:{self.pk} for {self.payment_id} [{self.status}]"