---
hide:
  - navigation
---

# Try the demo

## Setup

This lets you run the compose application locally and demo it:

```bash
# copy default conf
cp .env.example .env

# start the stack
docker compose up --build -d

# deploy static files and migrate database
docker compose exec django python manage.py collectstatic --no-input
docker compose exec django python manage.py migrate --no-input

# A convenience start-up Django command is there
# to populate the database with testdata
docker compose exec django python manage.py populate_users
docker compose exec django python manage.py populate_data
```
After waiting little you'll be able to access all collections at http://0.0.0.0:7180/oapif/collections.

Three users are provided out of the box; they can be logged in with through basic authentication; all `123` for password:
- `demo_viewer`
- `demo_editor`
- `admin`

As expected `admin` can access Django Admin at http://0.0.0.0:7180/admin.

## Use from QGIS

When up and running you can access the REST API from QGIS like this:

- Go to `Layers` > `Add layer` > `Add WFS Layer...`
- Create a new connection
  - URL: `https://0.0.0.0:7180/oapif/`
  - Version: `OGC API - Features`
- Click OK and ignore choose to ignore the invalid certificate error and store the exception
- You should see the two layers in the list, select them and choose `add`.
