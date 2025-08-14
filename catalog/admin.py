from django.contrib import admin
from .models import Destination, TourPackage, PackageImage
# Register your models here.
@admin.register(Destination)
class DestinationAdmin(admin.ModelAdmin):
    list_display = ("name","country","city","slug")
    search_fields = ("name","country","city")
    prepopulated_fields = {"slug": ("name","country")}

@admin.register(TourPackage)
class TourPackageAdmin(admin.ModelAdmin):
    list_display = ("title","destination","duration_days","base_price","currency","is_active")
    search_fields = ("title","destination__name")
    prepopulated_fields = {"slug": ("title",)}

@admin.register(PackageImage)
class PackageImageAdmin(admin.ModelAdmin):
    list_display = ("package","caption","order")