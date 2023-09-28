from django.contrib.auth.models import Group, Permission, User
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Populate db with groups, set permissions, add users"

    @transaction.atomic
    def handle(self, *args, **options):
        """Populate db with groups, set permissions, add users"""
        adding = []
        modifying = []
        viewing = []

        for model in ("point_2056_10fields", "nogeom_10fields"):
            adding.append(Permission.objects.get(codename=f"add_{model}"))
            modifying.append(Permission.objects.get(codename=f"change_{model}"))
            viewing.append(Permission.objects.get(codename=f"view_{model}"))

        editing = adding + modifying + viewing

        editors, _ = Group.objects.get_or_create(name="editors")
        viewers, _ = Group.objects.get_or_create(name="viewers")

        editors.save()
        viewers.save()

        editors.permissions.set(editing)
        viewers.permissions.set(viewing)

        a_viewer, _ = User.objects.get_or_create(username="demo_viewer")
        a_viewer.set_password("123")
        an_editor, _ = User.objects.get_or_create(username="demo_editor")
        an_editor.set_password("123")
        a_super_user = User.objects.create_superuser(username="admin", is_staff=True)
        a_super_user.set_password("123")

        a_viewer.save()
        an_editor.save()
        a_super_user.save()

        an_editor.groups.add(editors)
        a_viewer.groups.add(viewers)

        print(
            f"👥 added users 'demo_editor' & 'demo_viewer' to group 'editors' and 'viewers' respectively. Permissions set accordingly."
        )
