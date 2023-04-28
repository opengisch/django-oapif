from django.core.management import call_command
from django.core.management.base import BaseCommand

from . import populate_signs_poles, populate_users

user_options = {
    "data": lambda: call_command(populate_signs_poles.Command()),
    "users": lambda: call_command(populate_users.Command()),
    "superuser": lambda: call_command("createsuperuser"),
}


class Command(BaseCommand):
    help = "Initialize db with testdata, users and/or superuser"

    def add_arguments(self, parser):
        for opt in user_options:
            parser.add_argument(f"--{opt}", action="store_true")

    def handle(self, *args, **kwargs):
        defaults = {"data", "users"}
        commands = {
            user_options[key]
            for key in kwargs
            if key in user_options and (key in defaults or kwargs[key])
        }

        for cmd in commands:
            cmd()

        print(f"🎉 All set up!")
