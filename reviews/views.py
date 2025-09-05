from rest_framework import viewsets, permissions, filters
from .models import Review
from .serializers import ReviewSerializer
from permissions import IsOwnerOrReadOnly
from rest_framework.permissions import AllowAny
from rest_framework import viewsets, permissions, filters
from rest_framework.permissions import AllowAny, IsAuthenticated
from .models import Review
from .serializers import ReviewSerializer
from permissions import IsOwnerOrReadOnly

class ReviewViewSet(viewsets.ModelViewSet):
    queryset = Review.objects.select_related("user").all()
    serializer_class = ReviewSerializer
    filter_backends = (filters.SearchFilter, filters.OrderingFilter)
    search_fields = ("title", "body", "user__username")
    ordering_fields = ("rating", "created_at")

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]
        elif self.action == 'create':
            return [IsAuthenticated()]
        return [IsAuthenticated(), IsOwnerOrReadOnly()]

    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated and user.is_staff:
            return self.queryset
        return self.queryset.filter(is_approved=True)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)