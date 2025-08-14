from django.contrib import admin
from django.utils.html import mark_safe
from .models import User
# Register your models here.
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("username", "email", "role", "is_staff", "is_active", "avatar_preview")
    list_filter = ("role", "is_staff", "is_active")
    search_fields = ("username", "email", "phone")
    readonly_fields = ("avatar_preview",)

    def avatar_preview(self, obj):
        # Works for CloudinaryField or ImageField
        url = None
        if getattr(obj, "avatar", None):
            try:
                url = obj.avatar.url
            except Exception:
                url = None
        if url:
            return mark_safe(f'<img src="{url}" style="height:50px;border-radius:4px" />')
        return "-"
    avatar_preview.short_description = "Avatar"