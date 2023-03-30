# Signalo OAPIF

## Quickstart

```
# copy default conf
cp .env.example .env

# start the stack
docker compose up --build -d

# load fixtures (takes ~30s)
docker compose exec django python manage.py loaddata pole.json sign.json

# refresh computed fields (takes ~1min)
docker compose exec django python manage.py updatedata

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
