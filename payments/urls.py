from django.urls import path
from .views import CreatePaymentView, PaymentWebhookView, ChargeView

urlpatterns = [
    path("create/", CreatePaymentView.as_view(), name="payment-create"),
    path("charge/", ChargeView.as_view(), name="payment-charge"),
    path("webhook/<str:gateway>/", PaymentWebhookView.as_view(), name="payment-webhook"),
]
