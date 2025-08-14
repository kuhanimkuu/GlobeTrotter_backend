# finalproject_backend
GlobeTrotter Backend

GlobeTrotter is a Django REST Framework-based travel booking platform that allows users to explore and book hotels, rooms, and rental cars. It also supports reviews, media uploads via Cloudinary, and is ready for integration with external APIs like maps and payments.
Features (Current Progress)

    Hotels & Rooms
        Create hotels with details and specify multiple room types & quantities.
    Cars
        Manage rental cars with pricing, categories, and Cloudinary-hosted images.
    Reviews
        Add and manage user reviews for hotels, rooms, and cars.

    Admin Integration
        All models (Hotels, Rooms, Cars, Reviews) are fully registered in the Django admin panel for easy management.
    Media Uploads
        Images stored and delivered via Cloudinary.
    Serializers
        DRF serializers implemented for all models.

Upcoming Development
    API endpoints for CRUD operations on all models.
    External API integrations:
        Maps – For location-based searches and directions.
        Payments – For secure booking transactions.
    Authentication & user roles.
    Booking system for hotels, rooms, and cars.
    Review moderation and rating aggregation.

Tech Stack
    Backend: Django 5 + Django REST Framework
    Database: PostgreSQL
    Media Storage: Cloudinary
    Language: Python 3.13
    Hosting: TBD

