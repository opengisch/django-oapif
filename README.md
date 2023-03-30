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

# sprinkle some test data (refreshing computed fields is done from the command handler)
docker compose run django python manage.py gen_data

# wait a little, then check that https://localhost/oapif/collections/poles/items works from your browser
```

## Use from QGIS

Once up and running, you can use it from QGIS like this:

- Go to `Layers` > `Add layer` > `Add WFS Layer...`
- Create a new connection
  - URL: `https://localhost/oapif/`
  - Version: `OGC API - Features`
- Click OK and ignore choose to ignore the invalid certificate error and store the exception
- You should see the two layers in the list, select them and choose `add`.
