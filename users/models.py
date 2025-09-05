from django.db import models
from django.contrib.auth.models import AbstractUser
from cloudinary.models import CloudinaryField
# Create your models here.
class User(AbstractUser):
    class Role(models.TextChoices):
        CUSTOMER = 'CUSTOMER', 'Customer'
        AGENT = 'AGENT','Agent'
        ADMIN = 'ADMIN','Admin'
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.CUSTOMER)
    phone = models.CharField(max_length=30, blank=True, null=True)
    company = models.CharField(max_length=120, blank=True, null=True)
    
    avatar = CloudinaryField(
        "avatar", 
        blank=True, 
        null=True,
        
    )


    def is_customer(self): 
        return self.role == self.Role.CUSTOMER
    
    def is_organizer(self):
        return self.role == self.Role.AGENT
    
    def is_admin(self): 
        return self.role == self.Role.ADMIN

    def __str__(self):
        return f"{self.username} ({self.role})"