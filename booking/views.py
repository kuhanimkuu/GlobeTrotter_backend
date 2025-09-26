from rest_framework import viewsets, permissions, status, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, PermissionDenied
from django.shortcuts import get_object_or_404
from django.core.paginator import Paginator
import logging
from datetime import datetime
from adapters.maps import get_maps_adapter
from adapters.flights import get_flight_adapter
from adapters.maps import get_maps_adapter
from datetime import datetime
from decimal import Decimal
from .models import Booking
from .services import create_car_booking
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
    queryset = Booking.objects.select_related("user", "package").prefetch_related("items")
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return self.queryset.all()
        return self.queryset.filter(user=self.request.user)

    def get_serializer_class(self):
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
        serializer.save(user=self.request.user)

    def create(self, request, *args, **kwargs):
        if 'tour_package_id' in request.data:
            return self._create_tour_package_booking(request)
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


    logger = logging.getLogger(__name__)
    
    def resolve_airports_from_country(country_name: str) -> list:
        maps_adapter = get_maps_adapter("fake") 

        results = maps_adapter.geocode(query=country_name).get("results", [])
        
        airports = []
        for res in results:
            country = res.get("country")
            country_airports = maps_adapter.get_airports_by_country(country)
            airports.extend(country_airports)
        
        return airports


    @action(detail=False, methods=['post'])
    def flight(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        provider = validated_data["provider"]
        offer_id = validated_data["offer_id"]
        passengers = validated_data["passengers"]
        currency = validated_data.get("currency", "USD")
        try:
            from adapters.flights import get_flight_adapter
            flight_adapter = get_flight_adapter(provider)

            booking_result = flight_adapter.book(
                offer_id=offer_id,
                passengers=passengers,
                contact={
                    "emailAddress": request.user.email if request.user and request.user.email else "test@example.com",
                    "phones": [
                        {"deviceType": "MOBILE", "countryCallingCode": "1", "number": "0000000000"}
                    ],
                },
            )
            from decimal import Decimal
            booking_obj = Booking.objects.create(
                user=request.user,
                total=Decimal(booking_result["total_amount"]),
                currency=booking_result.get("currency", currency),
                note="Flight booking",
                external_reference=booking_result.get("external_booking_id") or booking_result.get("locator"),
                external_service=provider,
                status=Booking.Status.CONFIRMED
            )

            return Response(
                {   
                    "id": booking_obj.id,
                    "provider": provider,
                    "external_booking_id": booking_result.get("locator"),
                    "status": booking_result.get("status"),
                    "currency": booking_result.get("currency", currency),
                    "total_amount": booking_result.get("total_amount"),
                    "passengers": booking_result.get("passengers", []),
                    "raw": booking_result.get("raw", {}),
                },
                status=status.HTTP_201_CREATED,
            )

        except ImportError:
            logger.error(f"Flight provider '{provider}' not supported")
            return Response(
                {"detail": f"Flight provider '{provider}' is not supported"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception as e:
            logger.exception(f"Flight booking failed with {provider}")
            return Response(
                {"detail": f"Failed to create flight booking: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, methods=['get'])
    def flight_status(self, request, pk=None):
        booking = self.get_object()

        if not booking.external_service or not booking.external_reference:
            return Response(
                {"detail": "This is not an external flight booking"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            from adapters.flights import get_flight_adapter
            flight_adapter = get_flight_adapter(booking.external_service)

            status_result = flight_adapter.get_pnr(
                locator=booking.external_reference,
                last_name=request.user.last_name or "",
            )

            return Response(
                {
                    "provider": booking.external_service,
                    "external_booking_id": booking.external_reference,
                    "status": status_result.get("status"),
                    "details": status_result.get("itinerary", {}),
                }
            )

        except Exception as e:
            logger.error(f"Failed to get flight status: {str(e)}")
            return Response(
                {"detail": "Failed to retrieve flight status", "error": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
    @action(detail=False, methods=['post'])
    def hotel(self, request):
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
    @action(detail=False, methods=['post'])
    def flight_search(self, request):
        data = request.data
        origin_airports = data.get("origin_airports", [])
        destination_airports = data.get("destination_airports", [])
        departure_date = data.get("departure_date")
        passengers = data.get("passengers", 1)
        package_start_date = data.get("package_start_date")

        if not origin_airports or not destination_airports or not departure_date:
            return Response(
                {"detail": "origin_airports, destination_airports, and departure_date are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            flight_adapter = get_flight_adapter("fake")
            package_start_dt = None
            if package_start_date:
                package_start_dt = datetime.strptime(package_start_date, "%Y-%m-%d")

            offers = []

            for origin_code in origin_airports:
                for dest_code in destination_airports:
                    if not origin_code or not dest_code:
                        continue

                    search_result = flight_adapter.search(
                        origin=origin_code,
                        destination=dest_code,
                        departure_date=departure_date,
                        adults=passengers
                    )

                    for offer in search_result.get("offers", []):
                        if package_start_dt:
                            first_segment = offer["itineraries"][0]["segments"][0]
                            departure_str = first_segment["departure"]["at"]
                            departure_dt = datetime.strptime(departure_str, "%Y-%m-%dT%H:%M:%SZ")

                            if departure_dt > package_start_dt:
                                continue

                        offers.append(offer)

            if not offers:
                return Response({"detail": "No flight options found."}, status=status.HTTP_404_NOT_FOUND)

            return Response({"offers": offers})

        except Exception as e:
            logger.exception("Flight search failed")
            return Response(
                {"detail": f"Flight search failed: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )
