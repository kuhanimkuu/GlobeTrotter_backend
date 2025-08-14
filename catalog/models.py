from django.db import models
from django.utils.text import slugify
from cloudinary.models import CloudinaryField


class Destination(models.Model):
    name = models.CharField(max_length=140)
    country = models.CharField(max_length=120)
    city = models.CharField(max_length=120, blank=True)
    short_description = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    slug = models.SlugField(max_length=160, unique=True)
    cover_image = CloudinaryField(
        "cover_image", blank=True, null=True,
        
    )
    class Meta:
        ordering = ["country", "name"]
        indexes = [
            models.Index(fields=["country", "city"]),
            models.Index(fields=["slug"]),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(f"{self.name}-{self.country}")[:160]
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name}, {self.country}"


class TourPackage(models.Model):
    destination = models.ForeignKey(Destination, on_delete=models.CASCADE, related_name="packages")
    title = models.CharField(max_length=240)
    slug = models.SlugField(max_length=260, unique=True, blank=True)
    summary = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    duration_days = models.PositiveSmallIntegerField()
    base_price = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="USD")
    inclusions = models.TextField(blank=True)
    exclusions = models.TextField(blank=True)
    max_capacity = models.PositiveIntegerField(null=True, blank=True, help_text="Max pax per departure (optional)")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    main_image = CloudinaryField(
        "main_image", blank=True, null=True,
        
    )


    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["destination", "is_active"]),
            models.Index(fields=["slug"]),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)[:260]
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} — {self.destination.name}"


class PackageImage(models.Model):
    package = models.ForeignKey(TourPackage, on_delete=models.CASCADE, related_name="images")
    image = CloudinaryField("image",)
    caption = models.CharField(max_length=200, blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"{self.package.title} — {self.caption or 'image'}"