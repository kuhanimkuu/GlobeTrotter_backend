from asyncio.log import logger
from urllib import request
from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.contenttypes.models import ContentType
from django_filters.rest_framework import DjangoFilterBackend
from datetime import datetime, timedelta
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from .models import Hotel, RoomType, Car, AvailabilitySlot, Flight
from .serializers import HotelSerializer, RoomTypeSerializer, CarSerializer, FlightSerializer
from django.db.models import Q
from adapters.flights.amadeus import AmadeusAdapter
from adapters.flights.duffel import DuffelAdapter
from django.conf import settings
from adapters.flights.fake import FakeFlightsAdapter
from rest_framework.permissions import AllowAny
from datetime import datetime, timedelta
class HotelViewSet(viewsets.ModelViewSet):
    queryset = Hotel.objects.prefetch_related("room_types") 
    serializer_class = HotelSerializer
    permission_classes = [AllowAny]
    filter_backends = (filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend)
    search_fields = ("name", "city", "country", "address")
    ordering_fields = ("name", "rating")
    filterset_fields = ("is_active", "city", "country")

    def perform_create(self, serializer):
        user = self.request.user
        if not user.is_authenticated:
            raise permissions.PermissionDenied("Authentication required to create a hotel.")
        if not (user.is_staff or getattr(user, "role", None) == "ORGANIZER"):
            raise permissions.PermissionDenied("Only staff or organizers can create hotels.")
      
        serializer.save(is_active=True)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        hotel = serializer.save(is_active=True)  
        return Response(self.get_serializer(hotel).data, status=status.HTTP_201_CREATED)

   
    @action(detail=False, methods=["POST"], url_path="search")
    def search_hotels(self, request):
        filters = request.data
        queryset = self.get_queryset()

        location = filters.get("location", "").strip()
        min_rating = filters.get("min_rating")
        max_rating = filters.get("max_rating")
        if location:
            queryset = queryset.filter(
                Q(city__icontains=location) |
                Q(country__icontains=location) |
                Q(name__icontains=location) |
                Q(address__icontains=location)
            )
        if min_rating is not None:
            queryset = queryset.filter(rating__gte=min_rating)
        if max_rating is not None:
            queryset = queryset.filter(rating__lte=max_rating)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


    @action(detail=True, methods=["get"], url_path="availability")
    def availability(self, request, pk=None):
        hotel = self.get_object()
        start = request.query_params.get("start")
        end = request.query_params.get("end")

        if not start or not end:
            return Response(
                {"detail": "start and end query params required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            start_date = datetime.fromisoformat(start).date()
            end_date = datetime.fromisoformat(end).date()
        except ValueError:
            return Response({"detail": "invalid date format"}, status=status.HTTP_400_BAD_REQUEST)
        if end_date <= start_date:
            return Response({"detail": "end must be after start"}, status=status.HTTP_400_BAD_REQUEST)

        ct = ContentType.objects.get_for_model(RoomType)
        slots = AvailabilitySlot.objects.filter(
            content_type=ct,
            object_id__in=hotel.room_types.values_list("id", flat=True),
            date__gte=start_date,
            date__lt=end_date
        )
        slot_map = {(s.object_id, s.date): s.available for s in slots}

        data = []
        for rt in hotel.room_types.all():
            current = start_date
            min_avail = None
            dates = []
            while current < end_date:
                avail = slot_map.get((rt.id, current), rt.quantity)
                dates.append({"date": current.isoformat(), "available": avail})
                if min_avail is None or avail < min_avail:
                    min_avail = avail
                current += timedelta(days=1)
            data.append({
                "room_type": RoomTypeSerializer(rt, context={"request": request}).data,
                "min_available": min_avail,
                "dates": dates
            })

        return Response(data)

class RoomTypeViewSet(viewsets.ModelViewSet):
    queryset = RoomType.objects.select_related("hotel")
    serializer_class = RoomTypeSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = (filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend)
    search_fields = ("name", "hotel__name", "hotel__city", "hotel__country")
    ordering_fields = ("base_price", "capacity")
    filterset_fields = ("hotel",)

    def perform_create(self, serializer):
        user = self.request.user
        if not user.is_authenticated:
            raise permissions.PermissionDenied("Authentication required to create a room type.")
        if not (user.is_staff or getattr(user, "role", None) == "ORGANIZER"):
            raise permissions.PermissionDenied("Only staff or organizers can create room types.")
        serializer.save()


class CarViewSet(viewsets.ModelViewSet):
    queryset = Car.objects.all().select_related("destination")
    serializer_class = CarSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = (filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend)
    search_fields = ("make", "model", "provider")
    ordering_fields = ("daily_rate", "make", "model")
    filterset_fields = ("provider", "category", "available", "destination")

    def perform_create(self, serializer):
        user = self.request.user
        if not user.is_authenticated:
            raise permissions.PermissionDenied("Authentication required to create a car.")
        if not (user.is_staff or getattr(user, "role", None) == "ORGANIZER"):
            raise permissions.PermissionDenied("Only staff or organizers can create cars.")
        serializer.save()

    @action(detail=False, methods=["get"], url_path="by-destination")
    def by_destination(self, request):
        cars = self.queryset
        if not cars.exists():
            return Response({}, status=status.HTTP_200_OK)

        grouped = {}
        for car in cars:
            dest = car.destination.name if car.destination else "Unknown"
            grouped.setdefault(dest, []).append(CarSerializer(car, context={"request": request}).data)
        return Response(grouped)

    from django.db.models import Q

    @action(detail=False, methods=["post"], url_path="search")
    def search(self, request):
        filters = request.data
        qs = self.queryset.all() 

        if filters.get("location"):
            loc = filters["location"]
            qs = qs.filter(
                Q(destination__name__icontains=loc) |
                Q(destination__city__icontains=loc) |
                Q(destination__country__icontains=loc)
            )

        if filters.get("type"):
            qs = qs.filter(category__iexact=filters["type"].strip())

        if filters.get("start_date") and filters.get("end_date"):
            qs = qs.filter(available=True)

        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

class AvailabilityView(APIView):
    def get(self, request):
        obj_type = request.query_params.get("type")
        ids = request.query_params.get("ids")
        start = request.query_params.get("start")
        end = request.query_params.get("end")

        if not obj_type or not ids or not start or not end:
            return Response(
                {"detail": "type, ids, start, and end query params are required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            start_date = datetime.fromisoformat(start).date()
            end_date = datetime.fromisoformat(end).date()
        except ValueError:
            return Response({"detail": "invalid date format"}, status=status.HTTP_400_BAD_REQUEST)
        if end_date <= start_date:
            return Response({"detail": "end must be after start"}, status=status.HTTP_400_BAD_REQUEST)

        ids = [int(i) for i in ids.split(",") if i.isdigit()]
        data = []

        if obj_type == "hotel":
            queryset = Hotel.objects.filter(id__in=ids, is_active=True).prefetch_related("room_types")
            if not queryset.exists():
                return Response([], status=status.HTTP_200_OK)

            for hotel in queryset:
                hotel_data = {"hotel": HotelSerializer(hotel, context={"request": request}).data, "room_types": []}
                ct = ContentType.objects.get_for_model(RoomType)
                slots = AvailabilitySlot.objects.filter(
                    content_type=ct,
                    object_id__in=hotel.room_types.values_list("id", flat=True),
                    date__gte=start_date,
                    date__lt=end_date
                )
                slot_map = {(s.object_id, s.date): s.available for s in slots}

                for rt in hotel.room_types.all():
                    dates = []
                    current = start_date
                    min_avail = None
                    while current < end_date:
                        avail = slot_map.get((rt.id, current), rt.quantity)
                        dates.append({"date": current.isoformat(), "available": avail})
                        if min_avail is None or avail < min_avail:
                            min_avail = avail
                        current += timedelta(days=1)
                    hotel_data["room_types"].append({
                        "room_type": RoomTypeSerializer(rt, context={"request": request}).data,
                        "min_available": min_avail,
                        "dates": dates
                    })
                data.append(hotel_data)

        elif obj_type == "roomtype":
            queryset = RoomType.objects.filter(id__in=ids)
            if not queryset.exists():
                return Response([], status=status.HTTP_200_OK)

            ct = ContentType.objects.get_for_model(RoomType)
            slots = AvailabilitySlot.objects.filter(
                content_type=ct,
                object_id__in=ids,
                date__gte=start_date,
                date__lt=end_date
            )
            slot_map = {(s.object_id, s.date): s.available for s in slots}

            for rt in queryset:
                dates = []
                current = start_date
                min_avail = None
                while current < end_date:
                    avail = slot_map.get((rt.id, current), rt.quantity)
                    dates.append({"date": current.isoformat(), "available": avail})
                    if min_avail is None or avail < min_avail:
                        min_avail = avail
                    current += timedelta(days=1)
                data.append({
                    "room_type": RoomTypeSerializer(rt, context={"request": request}).data,
                    "min_available": min_avail,
                    "dates": dates
                })

        elif obj_type == "car":
            queryset = Car.objects.filter(id__in=ids, available=True)
            if not queryset.exists():
                return Response([], status=status.HTTP_200_OK)

            ct = ContentType.objects.get_for_model(Car)
            slots = AvailabilitySlot.objects.filter(
                content_type=ct,
                object_id__in=ids,
                date__gte=start_date,
                date__lt=end_date
            )
            slot_map = {(s.object_id, s.date): s.available for s in slots}

            for car in queryset:
                dates = []
                current = start_date
                min_avail = None
                while current < end_date:
                    avail = slot_map.get((car.id, current), 1 if car.available else 0)
                    dates.append({"date": current.isoformat(), "available": avail})
                    if min_avail is None or avail < min_avail:
                        min_avail = avail
                    current += timedelta(days=1)
                data.append({
                    "car": CarSerializer(car, context={"request": request}).data,
                    "min_available": min_avail,
                    "dates": dates
                })

        else:
            return Response(
                {"detail": "invalid type, must be hotel|roomtype|car"},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(data)
class FlightViewSet(viewsets.ModelViewSet):
    serializer_class = FlightSerializer
    permission_classes = [AllowAny]
    filter_backends = (filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend)
    search_fields = ("origin", "destination", "airline")
    ordering_fields = ("departure_time", "price", "airline", "created_at")
    filterset_fields = ("origin", "destination", "airline", "provider")

    def get_queryset(self):
        return Flight.objects.all()

    @action(detail=False, methods=["get"], url_path="available")
    def available(self, request):
        qs = Flight.objects.filter(expires_at__gt=timezone.now()).order_by("departure_time")
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["post"], url_path="search")
    def search(self, request):
        origin = request.data.get("origin")
        destination = request.data.get("destination")
        departure_date = request.data.get("departure_date")
        passengers = int(request.data.get("passengers", 1))
        force_refresh = request.data.get("force_refresh", False)
        provider_name = request.data.get("provider", "fake").lower()  

        logger.debug(f"Flight search: {origin}->{destination} on {departure_date} using provider: {provider_name}")
        if not force_refresh:
            qs = Flight.objects.filter(expires_at__gt=timezone.now())
            if origin:
                qs = qs.filter(origin__iexact=origin.upper())
            if destination:
                qs = qs.filter(destination__iexact=destination.upper())
            if departure_date:
                qs = qs.filter(departure_time__date=departure_date)

            logger.debug(f"Filtered query found: {qs.count()} flights")
            if not origin and not destination and not departure_date:
                if qs.exists():
                    serializer = self.get_serializer(qs.order_by("departure_time"), many=True)
                    return Response(serializer.data)

            if qs.exists():
                serializer = self.get_serializer(qs, many=True)
                return Response(serializer.data)
        try:
            if provider_name == "amadeus":
                adapter = AmadeusAdapter(settings.ADAPTERS["flights.amadeus"])
            elif provider_name == "duffel":
                adapter = DuffelAdapter(settings.ADAPTERS["flights.duffel"])
            else:
                adapter = FakeFlightsAdapter() 

            response = adapter.search(
                origin=origin,
                destination=destination,
                departure_date=departure_date,
                adults=passengers,
            )

            offers = response.get("offers", [])
            logger.debug(f"Offers count: {len(offers)}")
            if not offers:
                logger.warning(f"{provider_name} returned empty offers array")
                logger.debug(f"Full {provider_name} response: {response}")
                return Response([], status=status.HTTP_200_OK)

            flights = []
            for offer in offers:
                itineraries = offer.get("itineraries", [])
                if not itineraries or not itineraries[0].get("segments"):
                    continue

                first_segment = itineraries[0]["segments"][0]
                last_segment = itineraries[0]["segments"][-1]

                flight_number = first_segment.get("number") or offer.get("id")
                airline = first_segment.get("carrierCode")
                origin_code = first_segment.get("departure", {}).get("iataCode")
                destination_code = last_segment.get("arrival", {}).get("iataCode")
                departure_time_str = first_segment.get("departure", {}).get("at")
                arrival_time_str = last_segment.get("arrival", {}).get("at")
                seats_available = offer.get("numberOfBookableSeats", 0)

                departure_time_obj = parse_datetime(departure_time_str) if departure_time_str else None
                arrival_time_obj = parse_datetime(arrival_time_str) if arrival_time_str else None
                departure_date_obj = departure_time_obj.date() if departure_time_obj else None

                price_info = offer.get("price", {})
                price = price_info.get("total") or 0
                currency = price_info.get("currency") or "USD"

                if not origin_code or not destination_code:
                    continue

                obj, created = Flight.objects.update_or_create(
                    provider=provider_name,
                    offer_id=offer.get("id"),
                    defaults={
                        "flight_number": flight_number,
                        "origin": origin_code,
                        "destination": destination_code,
                        "departure_time": departure_time_obj,
                        "arrival_time": arrival_time_obj,
                        "airline": airline,
                        "price": price,
                        "currency": currency,
                        "seats_available": seats_available,
                        "departure_date": departure_date_obj,
                        "expires_at": timezone.now() + timezone.timedelta(minutes=30),
                    },
                )
                flights.append(obj)

            serializer = self.get_serializer(flights, many=True)
            return Response(serializer.data)

        except Exception as e:
            logger.error(f"{provider_name} API error: {str(e)}", exc_info=True)
            return Response(
                {"error": f"Failed to fetch flight data from {provider_name} provider"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
