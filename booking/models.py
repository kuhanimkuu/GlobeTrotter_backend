from django.db import models
from decimal import Decimal
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from cloudinary.models import CloudinaryField

User = settings.AUTH_USER_MODEL


class Booking(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        CONFIRMED = "CONFIRMED", "Confirmed"
        CANCELLED = "CANCELLED", "Cancelled"

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="bookings"
    )
    package = models.ForeignKey(
        "catalog.TourPackage",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bookings",
        help_text="Optional link to a tour package"
    )

    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING
    )
    total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )
    currency = models.CharField(max_length=3, default="USD")
    note = models.TextField(blank=True, null=True)

    voucher = CloudinaryField(
        "voucher",
        blank=True,
        null=True,
        help_text="Optional upload of proof or travel voucher"
    )

    # External integrations support
    external_reference = models.CharField(
        max_length=255, blank=True, null=True,
        help_text="External provider booking ID"
    )
    external_service = models.CharField(
        max_length=100, blank=True, null=True,
        help_text="External provider name (Amadeus, Duffel, etc.)"
    )
    cancellation_reason = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status", "created_at"]),
        ]

    def __str__(self):
        return f"Booking {self.pk} by {self.user}"


class BookingItem(models.Model):
    booking = models.ForeignKey(
        Booking,
        on_delete=models.CASCADE,
        related_name="items"
    )

    # Generic relation so we can link to Car/Hotel/Flight/etc.
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey("content_type", "object_id")

    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )
    line_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )

    # External booking payload (for flights, APIs, etc.)
    external_data = models.JSONField(blank=True, null=True)

    class Meta:
        indexes = [models.Index(fields=["booking"])]

    def save(self, *args, **kwargs):
        # Always recalc line total
        self.line_total = (self.unit_price or Decimal("0.00")) * self.quantity
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Item {self.pk} of Booking {self.booking_id}"
