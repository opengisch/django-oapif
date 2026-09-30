# Benchmark

`tests/benchmark/main.py` times `/items` for five collections, three limits and both formats, in CRS84,
which reprojects the features, and in EPSG:2056, the CRS they are stored in. CI runs it on every pull
request, under gunicorn with persistent connections and without debug mode, as a deployment would, and
comments the median times, compared with those of the base branch. As runners differ too much from one
another for a comparison with the results of another run, a second server, from the same image and on
the same data, serves the `django_oapif` of the base branch, and the requests go to each server in turn.
Only the library differs: changes to the dependencies or to the test app are not compared, nor are the
cases that the library of the base branch does not serve, or not in the same format.

Runs of the same library differ by less than 4%, but for about one case in a few hundred, so the comment
only gives the changes of more than 6%. A case that changes by more is timed again, with 60 requests, as a
slow spell of the runner could make it look so: the comment gives that second timing, and the benchmark
fails if the case is still slower.

To run it locally, on the same stack:

```bash
export COMPOSE_FILE=tests/docker-compose.yml:tests/docker-compose.dev.yml:tests/docker-compose.benchmark.yml
docker compose up --build -d
docker compose exec django python manage.py migrate --no-input
docker compose exec django python manage.py populate_data -s 1000
scripts/download-fixtures.sh
docker compose exec django python manage.py loaddata polygon_2056
pip install -r requirements-bench.txt
python tests/benchmark/main.py
```

To compare with another branch, serve its library next to it:

```bash
mkdir -p /tmp/base && git archive main django_oapif | tar -x -C /tmp/base
docker compose run --detach --no-deps --name django_base --publish 7181:8000 \
  --volume /tmp/base/django_oapif:/usr/src/django_oapif django
python tests/benchmark/main.py --base-url http://localhost:7181/oapif/collections --base-name main
```

The results, a chart and the table of the comment, are written to `tests/benchmark/output/`.
