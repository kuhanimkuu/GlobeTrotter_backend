from rest_framework import viewsets, permissions, status, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, PermissionDenied
from django.shortcuts import get_object_or_404
from django.core.paginator import Paginator
import logging

from .models import Booking
from .serializers import (
    BookingReadSerializer, 
    BookingCreateSerializer,
    ExternalFlightBookingSerializer,
    HotelBookingSerializer,
    CarBookingSerializer
)
from .services import (
    create_tour_package_booking,
    create_hotel_booking,
    create_car_booking,
    create_generic_booking,
    cancel_booking,
    BookingError
)

logger = logging.getLogger(__name__)


class BookingViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """
    Booking API Endpoints
    
    Main endpoints:
    - list:    GET    /api/v1/booking/bookings/         -> list bookings
    - retrieve: GET    /api/v1/booking/bookings/{id}/   -> get booking details
    - create:   POST   /api/v1/booking/bookings/        -> create a booking
    
    Custom actions:
    - cancel:   POST   /api/v1/booking/bookings/{id}/cancel/ -> cancel booking
    - flight:   POST   /api/v1/booking/bookings/flight/    -> book a flight via external API
    - hotel:    POST   /api/v1/booking/bookings/hotel/     -> book a hotel
    - car:      POST   /api/v1/booking/bookings/car/       -> book a car
    - mine:     GET    /api/v1/booking/bookings/mine/      -> get user's bookings
    """

    queryset = Booking.objects.select_related("user", "package").prefetch_related("items")
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Return all bookings for staff, only user's bookings for regular users."""
        if self.request.user.is_staff:
            return self.queryset.all()
        return self.queryset.filter(user=self.request.user)

    def get_serializer_class(self):
        """Use appropriate serializer based on action."""
        if self.action in ["create", "update", "partial_update"]:
            return BookingCreateSerializer
        elif self.action == "flight":
            return ExternalFlightBookingSerializer
        elif self.action == "hotel":
            return HotelBookingSerializer
        elif self.action == "car":
            return CarBookingSerializer
        return BookingReadSerializer

    def perform_create(self, serializer):
        """Default create behavior."""
        serializer.save(user=self.request.user)

    def create(self, request, *args, **kwargs):
        """
        Create a generic booking or tour package booking.
        """
        # Handle legacy tour package format
        if 'tour_package_id' in request.data:
            return self._create_tour_package_booking(request)
        
        # Handle generic booking format
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        try:
            booking = serializer.save()
        except ValidationError as e:
            raise e
        except Exception as e:
            logger.error(f"Failed to create booking: {str(e)}")
            return Response(
                {"detail": "Failed to create booking", "error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

        read_serializer = BookingReadSerializer(booking, context={"request": request})
        return Response(read_serializer.data, status=status.HTTP_201_CREATED)

    def _create_tour_package_booking(self, request):
        """Handle legacy tour package booking format."""
        tour_package_id = request.data.get('tour_package_id')
        start_date = request.data.get('start_date')
        guests = request.data.get('guests', 1)
        currency = request.data.get('currency', 'USD')
        note = request.data.get('note', '')

        if not tour_package_id:
            raise ValidationError({"tour_package_id": "This field is required for tour package bookings."})

        try:
            booking = create_tour_package_booking(
                user=request.user,
                tour_package_id=tour_package_id,
                start_date=start_date,
                guests=guests,
                currency=currency,
                note=note
            )
        except BookingError as e:
            raise ValidationError({"detail": str(e)})
        except Exception as e:
            logger.error(f"Failed to create tour package booking: {str(e)}")
            return Response(
                {"detail": "Failed to create booking", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        read_serializer = BookingReadSerializer(booking, context={"request": request})
        return Response(read_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel a specific booking."""
        booking = self.get_object()

        if not (request.user.is_staff or booking.user == request.user):
            raise PermissionDenied("You do not have permission to cancel this booking.")

        try:
            cancel_booking(booking, by_user=(booking.user == request.user))
        except BookingError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Failed to cancel booking {booking.id}: {str(e)}")
            return Response(
                {"detail": "Failed to cancel booking", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response(
            {"detail": "Booking cancelled successfully."},
            status=status.HTTP_200_OK
        )

    @action(detail=False, methods=['post'])
    def flight(self, request):
        """
        Book a flight via external API (Amadeus/Duffel).
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        provider = validated_data.get('provider')
        offer_id = validated_data.get('offer_id')
        passengers = validated_data.get('passengers', [])
        currency = validated_data.get('currency', 'USD')
        note = validated_data.get('note', '')
        payment_token = validated_data.get('payment_token')

        try:
            # Import the appropriate flight adapter
            from adapters.flights import get_flight_adapter
            
            # Get the adapter for the specified provider
            flight_adapter = get_flight_adapter(provider)
            
            # Create the flight booking through the adapter
            booking_result = flight_adapter.create_booking(
                user=request.user,
                offer_id=offer_id,
                passengers=passengers,
                currency=currency,
                note=note,
                payment_token=payment_token
            )
            
            # Return the external booking confirmation
            return Response({
                'status': 'success',
                'provider': provider,
                'external_booking_id': booking_result.get('booking_id'),
                'local_booking_id': booking_result.get('local_booking_id'),
                'confirmation': booking_result.get('confirmation'),
                'total_amount': booking_result.get('total_amount'),
                'currency': booking_result.get('currency'),
                'passengers': booking_result.get('passengers', [])
            }, status=status.HTTP_201_CREATED)
            
        except ImportError:
            logger.error(f"Flight provider '{provider}' not supported")
            return Response(
                {"detail": f"Flight provider '{provider}' is not supported"},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Flight booking failed with {provider}: {str(e)}")
            return Response(
                {"detail": f"Failed to create flight booking: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['post'])
    def hotel(self, request):
        """Book a hotel room."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        room_type_id = validated_data.get('room_type_id')
        check_in_date = validated_data.get('check_in_date')
        check_out_date = validated_data.get('check_out_date')
        rooms = validated_data.get('rooms', 1)
        currency = validated_data.get('currency', 'USD')
        note = validated_data.get('note', '')

        try:
            booking = create_hotel_booking(
                user=request.user,
                room_type_id=room_type_id,
                check_in_date=check_in_date.strftime('%Y-%m-%d') if check_in_date else None,
                check_out_date=check_out_date.strftime('%Y-%m-%d') if check_out_date else None,
                rooms=rooms,
                currency=currency,
                note=note
            )
        except BookingError as e:
            raise ValidationError({"detail": str(e)})
        except Exception as e:
            logger.error(f"Failed to create hotel booking: {str(e)}")
            return Response(
                {"detail": "Failed to create hotel booking", "error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = BookingReadSerializer(booking, context={"request": request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'])
    def car(self, request):
        """Book a car."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        car_id = validated_data.get('car_id')
        start_date = validated_data.get('start_date')
        end_date = validated_data.get('end_date')
        currency = validated_data.get('currency', 'USD')
        note = validated_data.get('note', '')

        try:
            booking = create_car_booking(
                user=request.user,
                car_id=car_id,
                start_date=start_date.strftime('%Y-%m-%d') if start_date else None,
                end_date=end_date.strftime('%Y-%m-%d') if end_date else None,
                currency=currency,
                note=note
            )
        except BookingError as e:
            raise ValidationError({"detail": str(e)})
        except Exception as e:
            logger.error(f"Failed to create car booking: {str(e)}")
            return Response(
                {"detail": "Failed to create car booking", "error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = BookingReadSerializer(booking, context={"request": request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'])
    def mine(self, request):
        """Get current user's bookings with filters."""
        status_filter = request.query_params.get('status')
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 10))
        
        bookings = Booking.objects.filter(user=request.user)
        
        if status_filter:
            status_list = [s.strip().upper() for s in status_filter.split(',')]
            valid_statuses = [status[0] for status in Booking.Status.choices]
            filtered_statuses = [s for s in status_list if s in valid_statuses]
            
            if filtered_statuses:
                bookings = bookings.filter(status__in=filtered_statuses)
        
        bookings = bookings.order_by('-created_at').select_related('package').prefetch_related('items')
        
        # Pagination
        paginator = Paginator(bookings, page_size)
        try:
            page_obj = paginator.page(page)
        except Exception:
            page_obj = paginator.page(1)
        
        serializer = BookingReadSerializer(page_obj, many=True, context={"request": request})
        
        return Response({
            'results': serializer.data,
            'pagination': {
                'count': paginator.count,
                'pages': paginator.num_pages,
                'current_page': page_obj.number,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous(),
            }
        })

    @action(detail=True, methods=['get'])
    def flight_status(self, request, pk=None):
        """Get status of an external flight booking."""
        booking = self.get_object()
        
        if not booking.external_service or not booking.external_reference:
            return Response(
                {"detail": "This is not an external flight booking"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from adapters.flights import get_flight_adapter
            flight_adapter = get_flight_adapter(booking.external_service)
            flight_status = flight_adapter.get_booking_status(booking.external_reference)
            
            return Response({
                'provider': booking.external_service,
                'external_booking_id': booking.external_reference,
                'status': flight_status.get('status'),
                'details': flight_status.get('details', {})
            })
            
        except Exception as e:
            logger.error(f"Failed to get flight status: {str(e)}")
            return Response(
                {"detail": "Failed to retrieve flight status", "error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )