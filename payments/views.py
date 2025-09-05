import logging
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView
from rest_framework import views, status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from payments import services
from .services import initiate_payment_for_booking, handle_payment_webhook
from booking.models import Booking

logger = logging.getLogger(__name__)


class CreatePaymentView(views.APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        booking_id = request.data.get("booking_id")
        gateway = request.data.get("gateway", "stripe")
        idempotency_key = request.data.get("idempotency_key")
        return_urls = request.data.get("return_urls", {})

        booking = Booking.objects.filter(pk=booking_id, user=request.user).first()
        if not booking:
            return Response({"detail": "Booking not found"}, status=status.HTTP_404_NOT_FOUND)

        try:
            result = initiate_payment_for_booking(booking, gateway=gateway, idempotency_key=idempotency_key, return_urls=return_urls)
        except Exception as exc:
            logger.exception("Failed to initiate payment for booking=%s", booking_id)
            return Response({"detail": "Failed to initiate payment", "error": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        payment = result["payment"]
        adapter_resp = result["adapter_response"]
        return Response({"payment_id": payment.id, "adapter": adapter_resp}, status=status.HTTP_201_CREATED)


@method_decorator(csrf_exempt, name="dispatch")
class PaymentWebhookView(views.APIView):
    permission_classes = [AllowAny]

    def post(self, request, gateway=None, *args, **kwargs):
        # headers: normalize HTTP_* headers to a simple dict expected by adapters
        headers = {k[5:].replace("_", "-").lower(): v for k, v in request.META.items() if k.startswith("HTTP_")}
        try:
            resp = handle_payment_webhook(gateway or "stripe", payload=request.body, headers=headers)
        except Exception as exc:
            logger.exception("Webhook handling failed for gateway=%s", gateway)
            return Response({"detail": "webhook handling error", "error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"detail": "ok", "result": resp}, status=status.HTTP_200_OK)
class ChargeView(APIView):
    def post(self, request):
        data = request.data
        try:
            result = services.charge(
                provider=data["provider"],
                amount=data["amount"],
                currency=data["currency"],
                source=data["source"],
                **data.get("extra", {})
            )
            return Response(result, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)