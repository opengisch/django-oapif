# django-ogcapif

**WARNING** This is in under development. API will break. Do not use in production.

*django-ogcapif* allows to easily expose your Django models through an OGCAPI-Features endpoint. It is based on Django REST Framework.


## Quickstart

```
# copy default conf
cp .env.example .env

# start the stack
docker compose up --build -d

# deploy static files and migrate database
docker compose exec django python manage.py collectstatic --no-input
docker compose exec django python manage.py migrate --no-input

# A convenience start-up Django command is there to populate the database with testdata for each app:
docker compose exec django python manage.py populate_vl
docker compose exec django python manage.py populate_signs_poles
docker compose exec django python manage.py populate_edge_cases

# Wait a little, then check that https://localhost/oapif/collections/signalo_core.pole/items works from your browser
```

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
docker compose run conformance_test
```

Results will be stored to `_test_outputs\testng\...\emailable-report.html
