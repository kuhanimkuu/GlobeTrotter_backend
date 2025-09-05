from django.urls import path, include
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
    
)
from .views import RegisterView, MeView, UserListView, LogoutView

urlpatterns = [
    # Authentication
    path("auth/register/", RegisterView.as_view(), name="register"),
    path("auth/me/", MeView.as_view(), name="me"),

    # JWT endpoints
    path("auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/token/verify/", TokenVerifyView.as_view(), name="token_verify"),

    # Session-based login/logout (DRF built-in)
    path("auth/", include("rest_framework.urls")),  # adds /login/ and /logout/

    # Admin-only user listing
    path("list/", UserListView.as_view(), name="user-list"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),

]
