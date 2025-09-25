from django.urls import path
from .views import (
    CreatePaymentView,
    PaymentWebhookView,
    ChargeView,
    RefundRequestCreateView,
    RefundRequestActionView,
)

urlpatterns = [
    path("payments/", CreatePaymentView.as_view(), name="payment-create"),
    path("payments/charge/", ChargeView.as_view(), name="payment-charge"),
    path("payments/webhook/<str:gateway>/", PaymentWebhookView.as_view(), name="payment-webhook"),
    path(
        "payments/<int:payment_id>/refund-request/",
        RefundRequestCreateView.as_view(),
        name="refund-request",
    ),
    path(
        "refunds/<int:refund_id>/<str:action>/",
        RefundRequestActionView.as_view(),
        name="refund-action",
    ),
]
