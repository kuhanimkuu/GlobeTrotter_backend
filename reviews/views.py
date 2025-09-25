from rest_framework import viewsets, filters
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.contrib.contenttypes.models import ContentType
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
        queryset = self.queryset
        user = self.request.user

        if user.is_authenticated and user.is_staff:
            return queryset

        queryset = queryset.filter(is_approved=True)
        content_type_str = self.request.query_params.get("content_type")
        object_id = self.request.query_params.get("object_id")

        if content_type_str and object_id:
            try:
                if "." in content_type_str:
                    app_label, model = content_type_str.lower().split(".")
                    ct = ContentType.objects.get(app_label=app_label, model=model)
                else:
                    ct = ContentType.objects.get(model=content_type_str.lower())
                print(">>> Filtering reviews with:", ct.app_label, ct.model, object_id)
                queryset = queryset.filter(content_type=ct, object_id=int(object_id))
            except Exception as e:
                print(">>> ERROR:", e)
                queryset = queryset.none()

        return queryset
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user, is_approved=True)
