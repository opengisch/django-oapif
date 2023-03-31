from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Initialize db with testdata, users and/or superuser"

    def add_arguments(self, parser):
        parser.add_argument("--data", action="store_true")
        parser.add_argument("--users", action="store_true")
        parser.add_argument("--superuser", action="store_true")

    def handle(self, *args, **options):
        controller = {
            "data": lambda: call_command("populate_data"),
            "users": lambda: call_command("populate_users"),
            "superuser": lambda: call_command("createsuperuser"),
        }

        for k, command in controller.items():
            if not options or k in options:
                command()

        print(f"🎉 All set up!")
