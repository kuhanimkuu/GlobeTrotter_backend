from django.contrib import admin
from django.utils.html import mark_safe
from .models import Hotel, RoomType, Car
# Register your models here.
class RoomTypeInline(admin.TabularInline):
    model = RoomType
    extra = 0
    fields = ("name", "capacity", "base_price", "quantity", "image_preview")
    readonly_fields = ("image_preview",)

    def image_preview(self, obj):
        if getattr(obj, "image", None):
            try:
                return mark_safe(f'<img src="{obj.image.url}" style="height:50px;" />')
            except Exception:
                return "-"
        return "-"
    image_preview.short_description = "Room image"

@admin.register(Hotel)
class HotelAdmin(admin.ModelAdmin):
    list_display = ("name", "destination", "rating", "is_active", "cover_preview")
    list_filter = ("is_active",)
    search_fields = ("name", "destination__name")
    inlines = (RoomTypeInline,)
    readonly_fields = ("cover_preview",)

    def cover_preview(self, obj):
        if getattr(obj, "cover_image", None):
            try:
                return mark_safe(f'<img src="{obj.cover_image.url}" style="height:80px;" />')
            except Exception:
                return "-"
        return "-"
    cover_preview.short_description = "Cover"

@admin.register(RoomType)
class RoomTypeAdmin(admin.ModelAdmin):
    list_display = ("hotel", "name", "capacity", "base_price", "quantity")
    search_fields = ("hotel__name", "name")
    readonly_fields = ("image_preview",)

    def image_preview(self, obj):
        if getattr(obj, "image", None):
            try:
                return mark_safe(f'<img src="{obj.image.url}" style="height:50px;" />')
            except Exception:
                return "-"
        return "-"
    image_preview.short_description = "Image"

@admin.register(Car)
class CarAdmin(admin.ModelAdmin):
    list_display = ("make", "model", "category", "daily_rate", "available", "image_preview")
    list_filter = ("available", "category")
    search_fields = ("make", "model")
    readonly_fields = ("image_preview",)

    def image_preview(self, obj):
        if getattr(obj, "carimage", None):
            try:
                return mark_safe(f'<img src="{obj.carimage.url}" style="height:60px;" />')
            except Exception:
                return "-"
        return "-"
    image_preview.short_description = "Image"