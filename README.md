# Signalo OAPIF

## Quickstart

```
# copy default conf
cp .env.example .env

# start the stack
docker compose up --build -d

# deploy static files and migrate database
docker compose run django python manage.py collectstatic --no-input
docker compose run django python manage.py migrate --no-input

# A convenience start-up Django command is there to help you get started with testdata
# and users; call it without argument to let it populate the database with testdata, users and a superuser:
docker compose run django python manage.py init

# Alternatively pass it any combination of the following options: --data, --users, --superuser

# Wait a little, then check that https://localhost/oapif/collections/signalo_core.pole/items works from your browser
```

## Authentication & permissions

By default the viewsets under `signalo/core` use the `AllowAny` permissions class. You can override these app-level permissions for particular viewsets when registering their corresponding models. (Refer to https://www.django-rest-framework.org/api-guide/permissions/#api-reference for permission classes). Example:

    models.py
    ---------
    from rest_framework.permissions import DjangoModelPermissionsOrAnonReadOnly
    ...
    @register_oapif_viewset(
        custom_viewset_attrs={
            "permissions_classes": (DjangoModelPermissionsOrAnonReadOnly,)
        }
    )

## Use from QGIS

Once up and running, you can use it from QGIS like this:

- Go to `Layers` > `Add layer` > `Add WFS Layer...`
- Create a new connection
  - URL: `https://localhost/oapif/`
  - Version: `OGC API - Features`
- Click OK and ignore choose to ignore the invalid certificate error and store the exception
- You should see the two layers in the list, select them and choose `add`.
