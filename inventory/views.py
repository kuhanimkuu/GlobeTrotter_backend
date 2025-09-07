from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.contenttypes.models import ContentType
from django_filters.rest_framework import DjangoFilterBackend
from datetime import datetime, timedelta

from .models import Hotel, RoomType, Car, AvailabilitySlot, Flight
from .serializers import HotelSerializer, RoomTypeSerializer, CarSerializer, FlightSerializer


class HotelViewSet(viewsets.ModelViewSet):
    queryset = Hotel.objects.prefetch_related("room_types")  # removed is_active filter
    serializer_class = HotelSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
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
        # Ensure the hotel is active when created
        serializer.save(is_active=True)

    def create(self, request, *args, **kwargs):
        """Override create to return full hotel data after POST"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        hotel = serializer.save(is_active=True)  # make sure is_active=True
        return Response(self.get_serializer(hotel).data, status=status.HTTP_201_CREATED)

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
    queryset = Flight.objects.all()
    serializer_class = FlightSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = (filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend)
    search_fields = ("origin", "destination", "airline")
    ordering_fields = ("departure_time", "price", "airline")
    filterset_fields = ("origin", "destination", "airline")

    @action(detail=False, methods=["post"], url_path="search")
    def search(self, request):
        origin = request.data.get("origin")
        destination = request.data.get("destination")
        departure_date = request.data.get("departure_date")

        qs = self.queryset
        if origin:
            qs = qs.filter(origin__iexact=origin)
        if destination:
            qs = qs.filter(destination__iexact=destination)
        if departure_date:
            qs = qs.filter(departure_time__date=departure_date)

        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)
