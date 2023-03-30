from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType

from signalo.core.models import Pole, Sign

content_type = ContentType.objects.get_for_model(Pole)
content_type = ContentType.objects.get_for_model(Sign)

can_add_poles = Permission.objects.create(
    codename="can_add_poles", name="Can add poles", content_type=content_type
)

can_see_poles = Permission.objects.create(
    codename="can_see_poles", name="Can see poles", content_type=content_type
)

can_add_signs = Permission.objects.create(
    codename="can_add_signs", name="Can add sign", content_type=content_type
)

can_see_signs = Permission.objects.create(
    codename="can_see_signs", name="Can see signs", content_type=content_type
)
