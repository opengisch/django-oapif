# Deployment

## Database connections

Use persistent database connections. PostGIS prepares each reprojection once per connection, then keeps
it: without them, every request for features in another CRS than the one they are stored in pays for it
again, about 130 ms on the test stack, against well under a millisecond once it is prepared. CRS84, the
default, is such a CRS for any collection stored in a projected one.

Under a WSGI server such as gunicorn, keep connections for a while with
[`CONN_MAX_AGE`](https://docs.djangoproject.com/en/stable/ref/settings/#conn-max-age), and have Django
check one before reusing it with
[`CONN_HEALTH_CHECKS`](https://docs.djangoproject.com/en/stable/ref/settings/#conn-health-checks), in case
the database closed it meanwhile, after a restart for instance:

```python
DATABASES["default"]["CONN_MAX_AGE"] = 600
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True
```

Keep the age finite, and under any idle timeout between Django and the database. Each worker thread keeps a
connection of its own, so the workers and threads of every instance have to fit within the
`max_connections` of PostgreSQL, or to go through a connection pooler such as pgbouncer.

Under ASGI, Django advises against persistent connections: use its
[connection pool](https://docs.djangoproject.com/en/stable/ref/databases/#postgresql-pool) instead, which
needs psycopg 3 and `psycopg[pool]`, with `CONN_MAX_AGE` left at 0. Each connection of the pool prepares a
reprojection once, then keeps it too.

```python
DATABASES["default"]["OPTIONS"] = {"pool": True}
```

Django's development server opens a new connection for every request, whatever the settings.

## Behind a reverse proxy

The responses link to other resources with absolute URLs: the landing page to the collections, a page of
items to the next one, a created feature to itself in its `Location` header. Django builds them from the
request, so behind a reverse proxy that terminates HTTPS, it has to be told which requests came in over
HTTPS, or the links point to `http://`. If the proxy sets `X-Forwarded-Proto`, and overwrites any that the
client sent:

```python
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
```

If the proxy does not pass the original `Host` on either, but sets `X-Forwarded-Host`, set
[`USE_X_FORWARDED_HOST`](https://docs.djangoproject.com/en/stable/ref/settings/#use-x-forwarded-host) too.
Read the warnings of the Django documentation on
[`SECURE_PROXY_SSL_HEADER`](https://docs.djangoproject.com/en/stable/ref/settings/#secure-proxy-ssl-header)
before setting it.
