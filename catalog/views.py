import logging
from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied
from inventory.models import RoomType, Hotel, Car, AvailabilitySlot
from .models import Destination, TourPackage
from .serializers import DestinationSerializer, TourPackageSerializer
from inventory.serializers import RoomTypeSerializer
from booking.models import Booking  
from reviews.models import Review    
from django.db.models import Sum
from django.utils import timezone

logger = logging.getLogger(__name__)


class DestinationViewSet(viewsets.ModelViewSet):
    queryset = Destination.objects.all()
    serializer_class = DestinationSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = (filters.SearchFilter, filters.OrderingFilter)
    search_fields = ("name", "country", "city")
    ordering_fields = ("name", "country")
    lookup_field = "slug"

    def list(self, request, *args, **kwargs):
        logger.info("Destination list requested by user=%s", request.user)
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        slug = kwargs.get("slug")
        logger.info("Destination detail requested: slug=%s by user=%s", slug, request.user)
        return super().retrieve(request, *args, **kwargs)


class TourPackageViewSet(viewsets.ModelViewSet):
    queryset = TourPackage.objects.filter(is_active=True)
    serializer_class = TourPackageSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = (filters.SearchFilter, filters.OrderingFilter)
    search_fields = ("title", "destination__name")
    ordering_fields = ("base_price", "duration_days", "created_at")
    lookup_field = "id"
    def _user_can_modify(self, user):
        return user.is_staff or user.is_organizer()
    def create(self, request, *args, **kwargs):
        logger.debug(" Incoming create request data: %s", request.data)
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            logger.error(" Validation errors: %s", serializer.errors)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def perform_create(self, serializer):
        user = self.request.user
        logger.info("TourPackage create attempt by user=%s | data=%s", user, self.request.data)
        if not (user.is_staff or user.is_organizer()):
            logger.warning("Unauthorized package create attempt by user=%s", user)
            raise PermissionDenied("Only staff or organizers can create tour packages.")
        instance = serializer.save()
        logger.info(" TourPackage created: id=%s, title=%s", instance.id, instance.title)

    def perform_update(self, serializer):
        user = self.request.user
        logger.info("TourPackage update attempt by user=%s | data=%s", user, self.request.data)
        if not (user.is_staff or user.is_organizer()):
            logger.warning("Unauthorized package update attempt by user=%s", user)
            raise PermissionDenied("Only staff or organizers can update tour packages.")
        instance = serializer.save()
        logger.info(" TourPackage updated: id=%s, title=%s", instance.id, instance.title)

    def perform_destroy(self, instance):
        user = self.request.user
        logger.info("TourPackage delete attempt by user=%s | package=%s", user, instance)
        if not self._user_can_modify(user):
            logger.warning("Unauthorized package delete attempt by user=%s", user)
            raise PermissionDenied("Only staff or organizers can delete tour packages.")
        instance.delete()
        logger.info(" TourPackage deleted: id=%s, title=%s", instance.id, instance.title)

  
    @action(detail=True, methods=["get"], permission_classes=[permissions.AllowAny])
    def rooms(self, request, slug=None):
        logger.info("Fetching rooms for package slug=%s by user=%s", slug, request.user)
        package = get_object_or_404(TourPackage, slug=slug)
        room_types = RoomType.objects.filter(hotel__destination=package.destination)
        serializer = RoomTypeSerializer(room_types, many=True, context={"request": request})
        logger.debug("Rooms found for package slug=%s: %s", slug, serializer.data)
        return Response(serializer.data)

    @action(detail=True, methods=["get"], permission_classes=[permissions.AllowAny])
    def availability(self, request, slug=None):
        logger.info("Fetching availability for package slug=%s by user=%s", slug, request.user)
        package = get_object_or_404(TourPackage, slug=slug)
        slots = AvailabilitySlot.objects.filter(package=package)
        data = [
            {
                "id": slot.id,
                "start_date": slot.start_date,
                "end_date": slot.end_date,
                "available_capacity": slot.available_capacity,
            }
            for slot in slots
        ]
        logger.debug("Availability slots for package slug=%s: %s", slug, data)
        return Response(data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], permission_classes=[permissions.AllowAny])
    def calculate_price(self, request, slug=None):
        logger.info("Price calculation request for package slug=%s | payload=%s", slug, request.data)
        package = get_object_or_404(TourPackage, slug=slug)
        hotel_id = request.data.get("hotel_id")
        car_id = request.data.get("car_id")
        nights = int(request.data.get("nights", 1))
        car_days = int(request.data.get("car_days", 1))
        commission = float(request.data.get("commission", 0))  

        room_cost = 0
        car_cost = 0

        if hotel_id:
            hotel = get_object_or_404(Hotel, id=hotel_id)
            room = hotel.room_types.first()
            if room:
                room_cost = room.base_price * nights

        if car_id:
            car = get_object_or_404(Car, id=car_id)
            car_cost = car.daily_rate * car_days

        subtotal = package.base_price + room_cost + car_cost
        total_price = subtotal + (subtotal * commission / 100)

        result = {
            "package_base": float(package.base_price),
            "room_cost": float(room_cost),
            "car_cost": float(car_cost),
            "commission_percent": commission,
            "total_price": float(total_price),
        }

        logger.info("Price calculated for package slug=%s | result=%s", slug, result)
        return Response(result)
    @action(detail=True, methods=["get"], permission_classes=[permissions.IsAuthenticated])
    def agent_details(self, request, slug=None):
        """Detailed stats for agents/staff about a package."""
        package = get_object_or_404(TourPackage, slug=slug)

        if not (request.user.is_staff or request.user.is_organizer()):
            raise PermissionDenied("Only staff or organizers can view this information.")

        total_bookings = Booking.objects.filter(package=package).count()
        total_revenue = Booking.objects.filter(package=package).aggregate(
            total=Sum("total_price")
        )["total"] or 0

        commission_earned = (total_revenue * package.commission) / 100

        reviews = Review.objects.filter(package=package).values(
            "id", "user__username", "rating", "comment", "created_at"
        )

        result = {
            "id": package.id,
            "title": package.title,
            "expired": package.end_date and package.end_date < timezone.now(),
            "total_bookings": total_bookings,
            "total_revenue": float(total_revenue),
            "commission_earned": float(commission_earned),
            "reviews": list(reviews),
        }

        return Response(result, status=status.HTTP_200_OK)