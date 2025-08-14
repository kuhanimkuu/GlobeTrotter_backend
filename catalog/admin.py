from django.contrib import admin
from django.utils.html import mark_safe
from .models import Destination, TourPackage, PackageImage
# Register your models here.
class PackageImageInline(admin.TabularInline):
    model = PackageImage
    extra = 1
    readonly_fields = ("image_preview",)
    fields = ("image", "caption", "order", "image_preview")

    def image_preview(self, obj):
        if not obj or not getattr(obj, "image", None):
            return "-"
        try:
            url = obj.image.url
        except Exception:
            return "-"
        return mark_safe(f'<img src="{url}" style="height:60px;" />')
    image_preview.short_description = "Preview"

@admin.register(Destination)
class DestinationAdmin(admin.ModelAdmin):
    list_display = ("name", "country", "city", "slug", "cover_preview")
    search_fields = ("name", "country", "city")
    list_filter = ("country",)
    prepopulated_fields = {"slug": ("name", "country")}
    readonly_fields = ("cover_preview",)

    def cover_preview(self, obj):
        if getattr(obj, "cover_image", None):
            try:
                return mark_safe(f'<img src="{obj.cover_image.url}" style="height:60px;" />')
            except Exception:
                return "-"
        return "-"
    cover_preview.short_description = "Cover"

@admin.register(TourPackage)
class TourPackageAdmin(admin.ModelAdmin):
    list_display = ("title", "destination", "duration_days", "base_price", "currency", "is_active")
    list_filter = ("destination", "is_active")
    search_fields = ("title", "destination__name")
    prepopulated_fields = {"slug": ("title",)}
    inlines = (PackageImageInline,)
    readonly_fields = ("main_image_preview",)

    def main_image_preview(self, obj):
        if getattr(obj, "main_image", None):
            try:
                return mark_safe(f'<img src="{obj.main_image.url}" style="height:80px;" />')
            except Exception:
                return "-"
        return "-"
    main_image_preview.short_description = "Main image"