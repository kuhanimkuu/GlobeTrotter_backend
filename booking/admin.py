from django.contrib import admin
from .models import Booking, BookingItem
# Register your models here.
class BookingItemInline(admin.TabularInline):
    model = BookingItem
    extra = 0
    readonly_fields = ("line_total",)
    fields = ("content_type", "object_id", "start_date", "end_date", "quantity", "unit_price", "line_total")

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "status", "total", "currency", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("user__username", "user__email", "id")
    inlines = (BookingItemInline,)
    readonly_fields = ("total", "created_at")