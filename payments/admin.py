from django.contrib import admin
from django.utils.html import format_html
from .models import Payment
# Register your models here.
@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        'id', 
        'booking_link', 
        'gateway', 
        'amount_currency', 
        'status', 
        'txn_ref_short', 
        'created_at',
        'is_terminal'
    )
    list_filter = ('status', 'gateway', 'created_at', 'currency')
    search_fields = (
        'txn_ref', 
        'booking__id', 
        'idempotency_key',
        'booking__user__email',
        'booking__user__username'
    )
    readonly_fields = (
        'created_at', 
        'updated_at', 
        'is_terminal',
        'booking_link',
        'metadata_preview'
    )
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'booking_link',
                'gateway', 
                'status',
                'amount',
                'currency'
            )
        }),
        ('Transaction Details', {
            'fields': (
                'txn_ref',
                'idempotency_key',
                'is_terminal'
            )
        }),
        ('Metadata', {
            'fields': ('metadata_preview',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

    def booking_link(self, obj):
        if obj.booking:
            url = f"/admin/booking/booking/{obj.booking.id}/change/"
            return format_html('<a href="{}">Booking #{}</a>', url, obj.booking.id)
        return "No Booking"
    booking_link.short_description = "Booking"

    def amount_currency(self, obj):
        return f"{obj.amount} {obj.currency}"
    amount_currency.short_description = "Amount"
    amount_currency.admin_order_field = 'amount'

    def txn_ref_short(self, obj):
        if obj.txn_ref and len(obj.txn_ref) > 20:
            return f"{obj.txn_ref[:20]}..."
        return obj.txn_ref or "-"
    txn_ref_short.short_description = "Transaction Ref"

    def metadata_preview(self, obj):
        if obj.metadata:
            import json
            formatted_json = json.dumps(obj.metadata, indent=2, ensure_ascii=False)
            return format_html('<pre style="max-height: 300px; overflow: auto;">{}</pre>', formatted_json)
        return "No metadata"
    metadata_preview.short_description = "Metadata"

    def is_terminal(self, obj):
        return obj.is_terminal
    is_terminal.boolean = True
    is_terminal.short_description = "Terminal Status"

    actions = ['mark_as_refunded']

    def mark_as_refunded(self, request, queryset):
        updated = queryset.filter(status=Payment.Status.SUCCESS).update(status=Payment.Status.REFUNDED)
        self.message_user(request, f"{updated} payments marked as refunded.")
    mark_as_refunded.short_description = "Mark selected successful payments as refunded"

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        extra_context = extra_context or {}
        if object_id:
            payment = Payment.objects.get(id=object_id)
            if payment.booking:
                extra_context['related_booking'] = payment.booking
        return super().changeform_view(request, object_id, form_url, extra_context)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('booking', 'booking__user')