from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from inventory.models import RoomType, AvailabilitySlot  
from .models import Destination, TourPackage
from .serializers import DestinationSerializer, TourPackageSerializer
from inventory.serializers import RoomTypeSerializer
from rest_framework.exceptions import PermissionDenied
# Create your views here.

class DestinationViewSet(viewsets.ModelViewSet):
    queryset = Destination.objects.all()
    serializer_class = DestinationSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = (filters.SearchFilter, filters.OrderingFilter)
    search_fields = ("name", "country", "city")
    ordering_fields = ("name", "country")
    lookup_field = "slug"

class TourPackageViewSet(viewsets.ModelViewSet):
    queryset = TourPackage.objects.filter(is_active=True)
    serializer_class = TourPackageSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = (filters.SearchFilter, filters.OrderingFilter)
    search_fields = ("title", "destination__name")
    ordering_fields = ("base_price", "duration_days", "created_at")
    lookup_field = "slug"
    def perform_create(self, serializer):
        user = self.request.user
        if not (user.is_staff or user.groups.filter(name="Organizer").exists()):
            raise PermissionDenied("Only staff or organizers can create tour packages.")
        serializer.save()
    def perform_update(self, serializer):
        user = self.request.user
        if not (user.is_staff or user.groups.filter(name="Organizer").exists()):
            raise PermissionDenied("Only staff or organizers can update tour packages.")
        serializer.save()

    def perform_destroy(self, instance):
        user = self.request.user
        if not (user.is_staff or user.groups.filter(name="Organizer").exists()):
            raise PermissionDenied("Only staff or organizers can delete tour packages.")
        instance.delete()

    # ---- Extra endpoints ----
    @action(detail=True, methods=["get"], permission_classes=[permissions.AllowAny])
    def rooms(self, request, slug=None):
        """
        GET /api/v1/catalog/packages/{slug}/rooms/
        """
        package = get_object_or_404(TourPackage, slug=slug)
        room_types = RoomType.objects.filter(hotel__destination=package.destination)
        serializer = RoomTypeSerializer(room_types, many=True, context={"request": request})
        return Response(serializer.data)

    @action(detail=True, methods=["get"], permission_classes=[permissions.AllowAny])
    def availability(self, request, slug=None):
        """
        GET /api/v1/catalog/packages/{slug}/availability/
        """
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
        return Response(data, status=status.HTTP_200_OK)