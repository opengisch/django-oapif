# Signalo OAPIF

## Quickstart

```
# copy default conf
cp .env.example .env

# start the stack
docker compose up --build -d

# deploy static files and migrate database
docker compose exec django python manage.py collectstatic --no-input
docker compose exec django python manage.py migrate --no-input

# A convenience start-up Django command is there to help you get started with testdata
# and users; call it without argument to let it populate the database with testdata, users and a superuser:
docker compose exec django python manage.py init

# Alternatively pass it any combination of the following options: --data, --users, --superuser

# Wait a little, then check that https://localhost/oapif/collections/signalo_core.pole/items works from your browser
```

## Tests

To run all tests, launch the Compose application as shown in the [Quickstart](#quickstart). Then run

    docker compose exec django python manage.py test

## Authentication & permissions

By default the viewsets under `signalo/core` use the `DjangoModelPermissionsOrAnonReadOnly` permissions class. You can add model permissions when registering their corresponding viewsets, as `permission_classes`. (Refer to https://www.django-rest-framework.org/api-guide/permissions/#api-reference for permission classes). Example:

    models.py
    ---------
    from rest_framework import permissions
    from django_oapif.decorators import register_oapif_viewset

    @register_oapif_viewset(
        custom_viewset_attrs={
            "permission_classes": (permissions.DjangoModelPermissionsOrAnonReadOnly,)
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

## Run tests

You can run the OGC API conformance test suite like this:

```
docker compose up --build conformance_test
```

Results will be stored to `_test_outputs\testng\...\emailable-report.html
