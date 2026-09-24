from django.contrib.auth import get_permission_codename
from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.db import transaction
from django_oapif_tests.tests.oapif import oapif


class Command(BaseCommand):
    help = "Populate db with groups, set permissions, add users"

    @transaction.atomic
    def handle(self, *args, **options):
        """Populate db with groups, set permissions, add users"""
        adding = []
        modifying = []
        viewing = []
        deleting = []

        # the models of every registered collection, so that a new one cannot be left out
        for model in dict.fromkeys(collection.model for collection in oapif.collections.values()):
            permissions = Permission.objects.filter(content_type=ContentType.objects.get_for_model(model))
            for action, granted in (("add", adding), ("change", modifying), ("delete", deleting), ("view", viewing)):
                granted.append(permissions.get(codename=get_permission_codename(action, model._meta)))

        editing = adding + modifying + deleting + viewing

        editors, _ = Group.objects.get_or_create(name="editors")
        viewers, _ = Group.objects.get_or_create(name="viewers")
        viewers_wo_secret, _ = Group.objects.get_or_create(name="viewers_without_secret")

        editors.save()
        viewers.save()

        editors.permissions.set(editing)
        viewers.permissions.set(viewing)

        viewer, _ = User.objects.get_or_create(username="demo_viewer")
        viewer_wo_secret, _ = User.objects.get_or_create(username="demo_viewer_without_secret")
        editor, _ = User.objects.get_or_create(username="demo_editor")
        # got rather than created, like the others, so that the command can run again on the same database
        super_user, _ = User.objects.get_or_create(username="admin")
        super_user.is_staff = super_user.is_superuser = True

        for user in (viewer, viewer_wo_secret, editor, super_user):
            user.set_password("123")
            user.save()

        editor.groups.add(editors)
        viewer.groups.add(viewers)
        viewer_wo_secret.groups.add(viewers_wo_secret)

        print(
            "👥 added users 'demo_editor' & 'demo_viewer' to group 'editors' and 'viewers' respectively. Permissions set accordingly."
        )
