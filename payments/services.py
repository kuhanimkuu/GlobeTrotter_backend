import logging
from decimal import Decimal
from typing import Dict, Any, Optional
from django.db import transaction

from adapters.payments import get_payment_adapter
from .models import Payment, RefundRequest
from booking.models import Booking

logger = logging.getLogger(__name__)


def initiate_payment_for_booking(
    booking: Booking,
    gateway: str = "stripe",
    idempotency_key: Optional[str] = None,
    return_urls: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    if booking is None:
        raise ValueError("booking is required")

    gateway = (gateway or "stripe").lower()
    return_urls = return_urls or {}

    
    if getattr(booking, "status", None) == Booking.Status.CANCELLED:
        raise ValueError("Cannot pay for cancelled booking")

    with transaction.atomic():
        payment = None
        if idempotency_key:
            payment = Payment.objects.select_for_update().filter(
                booking=booking, gateway=gateway, idempotency_key=idempotency_key
            ).first()
        if payment is None:
            payment = Payment.objects.select_for_update().filter(
                booking=booking, gateway=gateway, status=Payment.Status.PENDING
            ).first()

        if payment is None:
            payment = Payment.objects.create(
                booking=booking,
                gateway=gateway,
                amount=booking.total,
                currency=booking.currency,
                status=Payment.Status.PENDING,
                idempotency_key=idempotency_key,
            )
    adapter = get_payment_adapter(gateway)
    try:
        adapter_resp = adapter.create_checkout(
            amount=str(payment.amount),
            currency=payment.currency,
            customer={"email": getattr(booking.user, "email", "") if booking.user else ""},
            metadata={"payment_id": payment.id, "booking_id": booking.id},
            return_urls=return_urls,
        )
    except Exception as exc:
        logger.exception("Payment adapter error for payment=%s gateway=%s", payment.id, gateway)
        payment.status = Payment.Status.REFUNDED
        payment.metadata = {**(payment.metadata or {}), "refund": adapter_resp}
        payment.save(update_fields=["status", "metadata", "updated_at"])
        raise
    txn_ref = adapter_resp.get("txn_ref") or adapter_resp.get("provider_id") or adapter_resp.get("id")
    payment.txn_ref = txn_ref or payment.txn_ref
    payment.metadata = {**(payment.metadata or {}), "adapter_response": adapter_resp}
    payment.save(update_fields=["txn_ref", "metadata"])

    return {"payment": payment, "adapter_response": adapter_resp}


def handle_payment_webhook(gateway: str, payload: bytes, headers: Dict[str, Any]) -> Dict[str, Any]:
    gateway = (gateway or "stripe").lower()
    adapter = get_payment_adapter(gateway)
    if hasattr(adapter, "verify_webhook"):
        ok = adapter.verify_webhook(payload=payload, headers=headers)
        if not ok:
            raise RuntimeError("Webhook signature verification failed")

    parsed = adapter.parse_webhook(payload=payload, headers=headers)
    event = parsed.get("event")
    txn_ref = parsed.get("txn_ref")
    internal_payment_id = parsed.get("payment_id") or (parsed.get("raw", {}) or {}).get("metadata", {}).get("payment_id")
    if event in ("payment_succeeded", "checkout.session.completed", "payment_intent.succeeded"):
        new_status = Payment.Status.SUCCESS
    elif event in ("payment_failed", "payment_intent.payment_failed"):
        new_status = Payment.Status.FAILED
    elif event in ("payment_canceled", "payment_intent.canceled"):
        new_status = Payment.Status.CANCELLED
    else:
        new_status = None

    with transaction.atomic():
        payment_obj = None
        if txn_ref:
            payment_obj = Payment.objects.select_for_update().filter(txn_ref=txn_ref).first()

        if not payment_obj and internal_payment_id:
            payment_obj = Payment.objects.select_for_update().filter(id=internal_payment_id).first()

        if not payment_obj:
            payment_obj = Payment.objects.create(
                booking=None,
                gateway=gateway,
                amount=parsed.get("amount") or 0,
                currency=(parsed.get("currency") or "USD"),
                status=Payment.Status.PENDING,
                txn_ref=txn_ref,
                metadata={"webhook_raw": parsed.get("raw") or parsed},
            )
        if new_status and payment_obj.status == new_status:
            return {"status": "already_processed", "payment_id": payment_obj.id}
        payment_obj.metadata = {**(payment_obj.metadata or {}), "webhook": parsed.get("raw") or parsed}
        if new_status:
            payment_obj.status = new_status
        if txn_ref:
            payment_obj.txn_ref = txn_ref
        payment_obj.save()
        if new_status == Payment.Status.SUCCESS and payment_obj.booking:
            try:
                from booking.services import confirm_booking_on_payment
                confirm_booking_on_payment(payment_obj.booking, payment_obj)
            except Exception:
                logger.exception("Failed to confirm booking for payment=%s", payment_obj.id)

    return {"status": "processed", "payment_id": payment_obj.id, "new_status": new_status}
def charge(provider, amount, currency, source, **kwargs):
    adapter = get_payment_adapter(provider)
    if not adapter:
        raise ValueError(f"Unsupported provider: {provider}")
    return adapter.charge(amount, currency, source, **kwargs)
def request_refund(payment: Payment, user, reason: str = "") -> RefundRequest:
    if payment.status != Payment.Status.SUCCESS:
        raise ValueError("Only successful payments can be refunded.")
    return RefundRequest.objects.create(payment=payment, requested_by=user, reason=reason)


def approve_refund(refund: RefundRequest, agent) -> RefundRequest:
    if refund.status != RefundRequest.Status.PENDING:
        raise ValueError("Refund is not pending.")

    payment = refund.payment
    if not payment or payment.status != Payment.Status.SUCCESS:
        raise ValueError("Refund can only be processed for successful payments.")

    refund.status = RefundRequest.Status.APPROVED
    refund.processed_by = agent
    refund.save(update_fields=["status", "processed_by", "updated_at"])

    adapter = get_payment_adapter(payment.gateway)
    try:
        adapter_resp = adapter.refund(
            txn_ref=payment.txn_ref,
            amount=str(refund.amount or payment.amount),
            currency=payment.currency,
            reason=refund.reason or "Customer requested refund",
        )
        refund.metadata = {**(refund.metadata or {}), "adapter_response": adapter_resp}
        refund.save(update_fields=["metadata"])

        logger.info("Refund processed via %s for payment=%s refund=%s",
                    payment.gateway, payment.id, refund.id)

    except Exception as exc:
        logger.exception("Refund execution failed for payment=%s", payment.id)
        refund.metadata = {**(refund.metadata or {}), "error": str(exc)}
        refund.save(update_fields=["metadata"])
        raise

    return refund


def reject_refund(refund: RefundRequest, agent, reason: str = "") -> RefundRequest:
    if refund.status != RefundRequest.Status.PENDING:
        raise ValueError("Refund is not pending.")
    refund.status = RefundRequest.Status.REJECTED
    refund.processed_by = agent
    if reason:
        refund.reason = (refund.reason or "") + f"\n[Rejected: {reason}]"
    refund.save(update_fields=["status", "processed_by", "reason", "updated_at"])
    return refund