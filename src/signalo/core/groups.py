from django.contrib.auth.models import Group

from signalo.core.permissions import (
    can_add_poles,
    can_add_signs,
    can_see_poles,
    can_see_signs,
)

adding_permissions = [can_add_poles, can_add_signs]
reading_pemissions = [[can_see_poles, can_see_signs]]

editor_user, _ = Group.objects.get_or_create(name="editor_user")
reader_user, _ = Group.objects.get_or_create(name="reader_user")

editor_user.permissions.set(adding_permissions + reading_pemissions)
reader_user.permissions.set(reading_pemissions)
