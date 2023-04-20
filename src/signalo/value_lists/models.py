import os

from django.core.files.storage import FileSystemStorage
from django.db import models

path_to_sign = os.path.abspath("/media_volume/official_signs")


class SignsFileSystemStorage(FileSystemStorage):
    def get_available_name(self, name, *args, **kwargs):
        if self.exists(name):
            os.remove(os.path.join(path_to_sign, name))
        return name


fs = SignsFileSystemStorage(location=path_to_sign)


class OfficialSignType(models.Model):
    id = models.CharField(primary_key=True, max_length=10)
    active = models.BooleanField(default=True)
    value_de = models.CharField(max_length=255, null=True, blank=True)
    value_fr = models.CharField(max_length=255, null=True, blank=True)
    value_it = models.CharField(max_length=255, null=True, blank=True)
    value_ro = models.CharField(max_length=255, null=True, blank=True)
    description_de = models.TextField(null=True, blank=True)
    description_fr = models.TextField(null=True, blank=True)
    description_it = models.TextField(null=True, blank=True)
    description_ro = models.TextField(null=True, blank=True)
    img_de = models.FileField(storage=fs)
    img_fr = models.FileField(storage=fs)
    img_it = models.FileField(storage=fs)
    img_ro = models.FileField(storage=fs)
    img_height = models.IntegerField(default=0)
    img_width = models.IntegerField(default=0)
    no_dynamic_inscription = models.IntegerField(default=0)
    default_inscription1 = models.CharField(max_length=255, null=True, blank=True)
    default_inscription2 = models.CharField(max_length=255, null=True, blank=True)
    default_inscription3 = models.CharField(max_length=255, null=True, blank=True)
    default_inscription4 = models.CharField(max_length=255, null=True, blank=True)
