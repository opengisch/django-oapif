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
docker compose -f docker-compose.tests.yml up --build conformance_test
```

Results will be stored to `_test_outputs\testng\...\emailable-report.html
