from __future__ import annotations
from decimal import Decimal
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime

from django.db import transaction
from django.db.models import Sum
from django.contrib.contenttypes.models import ContentType
from .models import Booking, BookingItem
from catalog.models import TourPackage
from payments.models import Payment
from adapters import get_sms_adapter, get_email_adapter, get_flights_adapter

logger = logging.getLogger(__name__)

class BookingError(Exception):
    pass

CONTENT_TYPE_MAP = {
    'package': ('catalog', 'tourpackage'),
    'hotel': ('inventory', 'hotel'),
    'room': ('inventory', 'roomtype'),
    'car': ('inventory', 'car'),
}

def get_content_type(item_type: str) -> ContentType:
  
    if item_type not in CONTENT_TYPE_MAP:
        raise BookingError(f"Unknown item type: {item_type}")
    
    app_label, model = CONTENT_TYPE_MAP[item_type]
    try:
        return ContentType.objects.get(app_label=app_label, model=model)
    except ContentType.DoesNotExist:
        raise BookingError(f"Content type for {app_label}.{model} not found")

def _calculate_line_total(unit_price: Decimal, quantity: int) -> Decimal:
    return (unit_price or Decimal("0.00")) * Decimal(quantity)

def _calculate_duration_days(start_date: str, end_date: str) -> int:

    start = datetime.strptime(start_date, "%Y-%m-%d").date()
    end = datetime.strptime(end_date, "%Y-%m-%d").date()
    duration = (end - start).days
    if duration <= 0:
        raise BookingError("End date must be after start date")
    return duration

@transaction.atomic
def create_generic_booking(
    user,
    items: List[Dict[str, Any]],
    currency: str = "USD",
    note: Optional[str] = None,
) -> Booking:
   
    if not items:
        raise BookingError("At least one booking item is required")

    # Parse and validate items
    parsed_items = []
    total_amount = Decimal("0.00")
    
    for item in items:
        item_type = item.get("type")
        content_type = get_content_type(item_type)
        
        # Get the content object
        model_class = content_type.model_class()
        try:
            content_object = model_class.objects.get(pk=item["id"])
        except model_class.DoesNotExist:
            raise BookingError(f"{item_type} with id {item['id']} not found")
        
        # Calculate line total
        quantity = int(item.get("quantity", 1))
        unit_price = Decimal(str(item.get("unit_price", "0.00")))
        line_total = _calculate_line_total(unit_price, quantity)
        total_amount += line_total
        
        parsed_items.append({
            "content_type": content_type,
            "object_id": item["id"],
            "content_object": content_object,
            "start_date": item.get("start_date"),
            "end_date": item.get("end_date"),
            "quantity": quantity,
            "unit_price": unit_price,
            "line_total": line_total,
        })

    # Create Booking
    booking = Booking.objects.create(
        user=user,
        total=total_amount,
        currency=currency,
        status=Booking.Status.PENDING,
        note=note or "",
        package=None,
    )

    # Create BookingItem rows
    for item in parsed_items:
        BookingItem.objects.create(
            booking=booking,
            content_type=item["content_type"],
            object_id=item["object_id"],
            start_date=item["start_date"],
            end_date=item["end_date"],
            quantity=item["quantity"],
            unit_price=item["unit_price"],
            line_total=item["line_total"],
        )

    return booking

@transaction.atomic
def create_tour_package_booking(
    user,
    tour_package_id: int,
    start_date: Optional[str] = None,
    guests: int = 1,
    currency: str = "USD",
    note: Optional[str] = None,
) -> Booking:
    """Create a booking for a tour package"""
    try:
        package = TourPackage.objects.get(pk=tour_package_id)
    except TourPackage.DoesNotExist:
        raise BookingError("Tour package not found")
    
    if not package.is_active:
        raise BookingError("Package is not active")

    # Capacity check
    if package.max_capacity:
        existing_qty = BookingItem.objects.filter(
            content_type=ContentType.objects.get_for_model(TourPackage),
            object_id=package.id,
            booking__status__in=[Booking.Status.CONFIRMED, Booking.Status.PENDING],
        ).aggregate(total=Sum('quantity'))['total'] or 0
        
        if (existing_qty + guests) > package.max_capacity:
            raise BookingError("Requested seats exceed package remaining capacity")

    # Calculate total
    total_price = package.base_price * guests

    # Create Booking
    booking = Booking.objects.create(
        user=user,
        package=package,
        total=total_price,
        currency=currency or package.currency or "USD",
        status=Booking.Status.PENDING,
        note=note or "",
    )

    # Create BookingItem
    BookingItem.objects.create(
        booking=booking,
        content_object=package,
        start_date=start_date,
        end_date=None,  
        quantity=guests,
        unit_price=package.base_price,
        line_total=total_price,
    )

    return booking

@transaction.atomic
def create_flight_booking(
    user,
    offer_id: str,
    passengers: List[Dict[str, Any]],
    payment_token: str,
    currency: str = "USD",
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    
    try:
        flights_adapter = get_flights_adapter() 
        
        # Call the external API through the adapter
        booking_result = flights_adapter.create_booking(
            offer_id=offer_id,
            passengers=passengers,
            payment_token=payment_token,
            currency=currency,
            notes=notes
        )
        
        # Create a local booking record for reference
        booking = Booking.objects.create(
            user=user,
            total=Decimal(str(booking_result.get('total_amount', '0.00'))),
            currency=currency,
            status=Booking.Status.CONFIRMED if booking_result.get('status') == 'confirmed' else Booking.Status.PENDING,
            note=notes or "",
            external_reference=booking_result.get('booking_id'),
            external_service=flights_adapter.get_service_name(),
        )
        
        # Store flight details as a booking item 
        BookingItem.objects.create(
            booking=booking,
            content_type=None, 
            object_id=None,
            start_date=booking_result.get('departure_date'),
            end_date=booking_result.get('return_date'),
            quantity=len(passengers),
            unit_price=Decimal(str(booking_result.get('total_amount', '0.00'))),
            line_total=Decimal(str(booking_result.get('total_amount', '0.00'))),
            external_data=booking_result,  
        )
        
        # Return both the external result and local booking reference
        return {
            'status': 'confirmed',
            'external_booking': booking_result,
            'local_booking_id': booking.id,
            'booking': booking
        }
        
    except Exception as e:
        logger.error(f"Flight booking failed: {str(e)}")
        raise BookingError(f"Flight booking failed: {str(e)}")

@transaction.atomic
def create_hotel_booking(
    user,
    room_type_id: int,
    check_in_date: str,
    check_out_date: str,
    rooms: int = 1,
    currency: str = "USD",
    note: Optional[str] = None,
) -> Booking:
    from inventory.models import RoomType
    
    try:
        room_type = RoomType.objects.get(pk=room_type_id)
    except RoomType.DoesNotExist:
        raise BookingError("Room type not found")
    
    # Calculate duration and total price
    duration = _calculate_duration_days(check_in_date, check_out_date)
    total_price = room_type.base_price * duration * rooms
    
    items = [{
        "type": "room",
        "id": room_type_id,
        "quantity": rooms,
        "unit_price": str(total_price),
        "start_date": check_in_date,
        "end_date": check_out_date,
    }]
    
    return create_generic_booking(user, items, currency or room_type.currency, note)

@transaction.atomic
def create_car_booking(
    user,
    car_id: int,
    start_date: str,
    end_date: str,
    currency: str = "USD",
    note: Optional[str] = None,
) -> Booking:
    from inventory.models import Car
    
    try:
        car = Car.objects.get(pk=car_id)
    except Car.DoesNotExist:
        raise BookingError("Car not found")
    
    if not car.available:
        raise BookingError("Car is not available for booking")
    
    # Calculate duration and total price
    duration = _calculate_duration_days(start_date, end_date)
    total_price = car.daily_rate * duration
    
    items = [{
        "type": "car",
        "id": car_id,
        "quantity": 1,
        "unit_price": str(total_price),
        "start_date": start_date,
        "end_date": end_date,
    }]
    
    return create_generic_booking(user, items, currency or car.currency, note)

@transaction.atomic
def confirm_booking_on_payment(booking: Booking, payment: Optional[Payment] = None) -> Booking:
    """Mark booking as CONFIRMED when payment succeeds"""
    if booking is None:
        raise BookingError("booking is required")

    booking = Booking.objects.select_for_update().get(pk=booking.pk)

    if booking.status == Booking.Status.CONFIRMED:
        logger.debug("Booking %s already confirmed", booking.pk)
        return booking

    booking.status = Booking.Status.CONFIRMED
    booking.save(update_fields=["status"])

    # Reduce inventory for tour packages
    try:
        for bi in booking.items.all():
            obj = bi.content_object
            if isinstance(obj, TourPackage) and getattr(obj, "max_capacity", None):
                obj.max_capacity = max(0, obj.max_capacity - bi.quantity)
                obj.save(update_fields=["max_capacity"])
    except Exception:
        logger.exception("Failed to decrement package capacity for booking %s", booking.pk)

    # Send confirmation notifications
    try:
        # Send SMS
        if hasattr(booking.user, 'phone') and booking.user.phone:
            try:
                sms_adapter = get_sms_adapter()
                sms_adapter.send_sms(
                    to=booking.user.phone,
                    message=f"Your booking #{booking.id} has been confirmed. Total: {booking.currency} {booking.total}"
                )
            except Exception as e:
                logger.warning("SMS notification failed: %s", str(e))

        # Send email
        if hasattr(booking.user, 'email') and booking.user.email:
            try:
                email_adapter = get_email_adapter()
                email_adapter.send_email(
                    to=[booking.user.email],
                    subject="Booking Confirmation",
                    html=f"""
                    <h2>Booking Confirmed</h2>
                    <p>Your booking #{booking.id} has been confirmed.</p>
                    <p><strong>Total Amount:</strong> {booking.currency} {booking.total}</p>
                    <p>Thank you for choosing our service!</p>
                    """
                )
            except Exception as e:
                logger.warning("Email notification failed: %s", str(e))
                
    except Exception as e:
        logger.error("Notification system error: %s", str(e))

    return booking

@transaction.atomic
def cancel_booking(booking: Booking, *, reason: Optional[str] = None, by_user: bool = True) -> Booking:
    if booking is None:
        raise BookingError("booking is required")

    booking = Booking.objects.select_for_update().get(pk=booking.pk)
    if booking.status == Booking.Status.CANCELLED:
        return booking
    if booking.external_service and booking.external_reference:
        try:
            flights_adapter = get_flights_adapter(booking.external_service)
            cancellation_result = flights_adapter.cancel_booking(booking.external_reference)
            if not cancellation_result.get('success', False):
                raise BookingError(f"External cancellation failed: {cancellation_result.get('message')}")
        except Exception as e:
            logger.error("External booking cancellation failed: %s", str(e))
            raise BookingError(f"Failed to cancel external booking: {str(e)}")

    booking.status = Booking.Status.CANCELLED
    booking.cancellation_reason = reason or ("Cancelled by user" if by_user else "Cancelled by staff")
    booking.save(update_fields=["status", "cancellation_reason"])
    try:
        for bi in booking.items.all():
            obj = bi.content_object
            if isinstance(obj, TourPackage) and getattr(obj, "max_capacity", None) is not None:
                obj.max_capacity = obj.max_capacity + bi.quantity
                obj.save(update_fields=["max_capacity"])
    except Exception:
        logger.exception("Failed to restore capacity for booking %s", booking.pk)

    return booking

def list_user_bookings(user, status: Optional[List[str]] = None):
    qs = Booking.objects.filter(user=user).order_by("-created_at")
    if status:
        qs = qs.filter(status__in=status)
    return qs

def get_user_booking(user, booking_id: int) -> Optional[Booking]:
    return Booking.objects.filter(pk=booking_id, user=user).first()

def get_booking_with_items(booking_id: int) -> Optional[Booking]:
    return Booking.objects.filter(pk=booking_id).prefetch_related('items').first()