from rest_framework.routers import DefaultRouter
from .views import DestinationViewSet, TourPackageViewSet

router = DefaultRouter()
router.register(r'destinations', DestinationViewSet, basename='destination')
router.register(r'packages', TourPackageViewSet, basename='tourpackage')

urlpatterns = router.urls
