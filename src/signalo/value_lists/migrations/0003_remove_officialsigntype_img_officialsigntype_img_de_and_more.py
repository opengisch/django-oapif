# Generated by Django 4.2 on 2023-04-17 16:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('signalo_vl', '0002_remove_officialsigntype_img_de_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='officialsigntype',
            name='img',
        ),
        migrations.AddField(
            model_name='officialsigntype',
            name='img_de',
            field=models.FileField(default='settings.MEDIA_ROOT/official_signs', upload_to='official_signs'),
        ),
        migrations.AddField(
            model_name='officialsigntype',
            name='img_fr',
            field=models.FileField(default='settings.MEDIA_ROOT/official_signs', upload_to='official_signs'),
        ),
        migrations.AddField(
            model_name='officialsigntype',
            name='img_it',
            field=models.FileField(default='settings.MEDIA_ROOT/official_signs', upload_to='official_signs'),
        ),
        migrations.AddField(
            model_name='officialsigntype',
            name='img_ro',
            field=models.FileField(default='settings.MEDIA_ROOT/official_signs', upload_to='official_signs'),
        ),
    ]
