from django.core.management.base import BaseCommand
from django.utils import timezone
from inventory.models import Flight


class Command(BaseCommand):
    help = "Delete expired flight offers from the database"

    def handle(self, *args, **options):
        now = timezone.now()
        expired = Flight.objects.filter(expires_at__lte=now)
        count = expired.count()
        expired.delete()
        self.stdout.write(
            self.style.SUCCESS(f"Deleted {count} expired flight offer(s).")
        )


"""to clean up expired flight offers, run:

python manage.py cleanup_expired_flights

"""