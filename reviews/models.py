from django.db import models
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

# Create your models here.
User = settings.AUTH_USER_MODEL

class Review(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reviews")
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type","object_id")
    rating = models.PositiveSmallIntegerField()  # 1..5
    title = models.CharField(max_length=200, blank=True)
    body = models.TextField(blank=True)
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    user_avatar_url = models.URLField(max_length=500, blank=True, null=True, help_text="Snapshot of user's avatar at time of review")
    class Meta:
        indexes = [models.Index(fields=["content_type","object_id"]), models.Index(fields=["user"])]