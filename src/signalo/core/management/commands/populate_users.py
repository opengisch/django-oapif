from django.contrib.auth.models import User, Group, Permission
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Populate db with groups, set permissions, add users"
        
    @transaction.atomic
    def handle(self, *args, **options):
        """Populate db with groups, set permissions, add users"""
        can_add_pole = Permission.objects.get(codename="add_pole")
        can_modify_pole = Permission.objects.get(codename="change_pole")
        can_view_pole = Permission.objects.get(codename="view_pole")
        can_add_sign = Permission.objects.get(codename="add_sign")
        can_modify_sign = Permission.objects.get(codename="change_sign")
        can_view_sign = Permission.objects.get(codename="view_sign")

        adding = [can_add_pole, can_add_sign]
        modifying = [can_modify_pole, can_modify_sign]
        viewing = [can_view_pole, can_view_sign]
        editing = adding + modifying + viewing

        editors = Group(name="editors")
        viewers = Group(name="viewers")
        editors.save()
        viewers.save()

        editors.permissions.set(editing)
        viewers.permissions.set(viewing)

        an_editor, _ = User.objects.get_or_create(username="Eddy")
        a_viewer, _ = User.objects.get_or_create(username="Viggo")

        a_viewer.save()
        an_editor.save()

        an_editor.groups.add(editors)
        a_viewer.groups.add(viewers)

        print(
            f"🤖 added user 'Eddy' to group 'editors' and user 'Viggo' to group 'viewers'. Permissions set accordingly."
        )
