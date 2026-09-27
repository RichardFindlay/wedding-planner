from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from planner import models as m
from planner import seed


class Command(BaseCommand):
    help = "Make sure Richard & Denver exist as people and load starter data into an empty database."

    def handle(self, *args, **options):
        User = get_user_model()
        for username, name in (("richard", "Richard"), ("denver", "Denver")):
            user, created = User.objects.get_or_create(username=username, defaults={"first_name": name})
            if created:
                # No passwords — you just pick who you are on each device.
                user.set_unusable_password()
            user.first_name = name
            user.is_staff = user.is_superuser = True
            user.save()

        if not (m.Task.objects.exists() or m.Venue.objects.exists() or m.BudgetCategory.objects.exists()):
            self.stdout.write("Empty database — loading starter plan.")
            seed.run()
        self.stdout.write(self.style.SUCCESS("Ready."))
