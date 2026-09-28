# Try the demo

The repository has a Docker Compose stack, which serves the test app of django-oapif, with a collection for each
case the tests cover.

## Setup

```bash
# copy the default configuration
cp .env.example .env

# start the stack
docker compose up --build -d

# deploy the static files and migrate the database
docker compose exec django python manage.py collectstatic --no-input
docker compose exec django python manage.py migrate --no-input

# create the demo users, and fill the collections with test data
docker compose exec django python manage.py populate_users
docker compose exec django python manage.py populate_data
```

The collections are then served at http://0.0.0.0:7180/oapif/collections.

The demo users log in with HTTP Basic, with `123` as password:

| User                           | Permissions                                                                       |
|--------------------------------|-----------------------------------------------------------------------------------|
| `demo_viewer`                  | reads every collection                                                            |
| `demo_editor`                  | reads and writes every collection                                                 |
| `demo_viewer_without_secret`   | reads the collections that anyone may read                                        |
| `admin`                        | a superuser, who can log in to the Django admin site at http://0.0.0.0:7180/admin |

Most collections may be read by anyone, `tests.secretlayer` by the users with its permissions only.

## Use from QGIS

- Go to `Layer` > `Add Layer` > `Add WFS / OGC API - Features Layer…`
- Create a new connection
    - URL: `http://0.0.0.0:7180/oapif/`
    - Version: `OGC API - Features`
    - Authentication: `Basic`, with one of the demo users, to edit the features or see the secret layer
- Connect, select the collections, and click `Add`.
