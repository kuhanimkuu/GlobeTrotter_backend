from rest_framework.routers import DefaultRouter
from .views import HotelViewSet, RoomTypeViewSet, CarViewSet, AvailabilityView
from django.urls import path, include
router = DefaultRouter()
router.register(r'hotels', HotelViewSet, basename='hotel')
router.register(r'room-types', RoomTypeViewSet, basename='roomtype')
router.register(r'cars', CarViewSet, basename='car')

urlpatterns = [
    path("", include(router.urls)),
    path("availability/", AvailabilityView.as_view(), name="availability"),
]
