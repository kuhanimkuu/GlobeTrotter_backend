from django.db import models
from decimal import Decimal
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from cloudinary.models import CloudinaryField

# Create your models here.
class Hotel(models.Model):
    name = models.CharField(max_length=180)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, default='Unknown')
    country = models.CharField(max_length=100, default='Unknown')
    destination = models.CharField(max_length=255, blank=True, null=True)
    rating = models.DecimalField(max_digits=2, decimal_places=1, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True)  # <-- add this
    cover_image = CloudinaryField(
        "image",
        folder="globetrotter/hotels",
        resource_type="image",
        use_filename=True,
        unique_filename=False,
        blank=True,
        null=True,
    )


    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["country","city","is_active"])]

    def __str__(self): 
        return self.name


class RoomType(models.Model):
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name="room_types")
    name = models.CharField(max_length=120)  
    capacity = models.PositiveIntegerField(default=2)
    base_price = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="USD")
    quantity = models.PositiveIntegerField(default=1, help_text="Number of available rooms of this type")
    availability = models.PositiveBigIntegerField(default=1, help_text='Number of currently available rooms of this type')
    image = CloudinaryField(
        "image",
        folder="globetrotter/rooms",
        resource_type="image",
        use_filename=True,
        unique_filename=False,
        blank=True,
        null=True,
    )

    class Meta:
        unique_together = ("hotel","name")
        indexes = [models.Index(fields=["hotel","name"])]

    def __str__(self): 
        return f"{self.hotel.name} — {self.name}"


class Car(models.Model):
    destination = models.ForeignKey(
        "catalog.Destination",
        on_delete=models.CASCADE,
        related_name="cars"
    )
    provider = models.CharField(max_length=120, blank=True)
    make = models.CharField(max_length=80)
    model = models.CharField(max_length=80)
    category = models.CharField(max_length=50)  
    daily_rate = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="USD")
    available = models.BooleanField(default=True)
    driver_name = models.CharField(max_length=255, blank=True, null=True)
    driver_contact = models.CharField(max_length=50, blank=True, null=True)
    carimage = CloudinaryField(
        "image",
        folder="globetrotter/cars",
        resource_type="image",
        use_filename=True,
        unique_filename=False,
        blank=True,
        null=True,
    )
    
    def __str__(self): 
        return f"{self.make} {self.model} ({self.category})"


class AvailabilitySlot(models.Model):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    date = models.DateField()
    available = models.IntegerField(default=0, help_text="Units available for this date")
   
    class Meta:
        unique_together = ("content_type","object_id","date")
        indexes = [models.Index(fields=["date"])]
# inventory/models.py
from django.db import models
from decimal import Decimal


class Flight(models.Model):
    provider = models.CharField(max_length=100, help_text="e.g. Amadeus, Duffel, Fake")
    offer_id = models.CharField(max_length=255, help_text="Reference to external API offer")
    origin = models.CharField(max_length=3)
    destination = models.CharField(max_length=3)
    departure_date = models.DateField()
    return_date = models.DateField(null=True, blank=True)

    price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    currency = models.CharField(max_length=3, default="USD")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.origin} → {self.destination} ({self.departure_date})"
