FROM python:3.13-slim-bookworm

WORKDIR /app

# Unbuffered stdout
ENV PYTHONUNBUFFERED=1

COPY requirements-prod.txt .
RUN pip install --no-cache-dir -r requirements-prod.txt

COPY manage.py .
COPY healthcheck.py .
COPY config ./config
COPY core ./core
COPY auth_app ./auth_app
COPY cleanuparr ./cleanuparr
COPY nzbdav ./nzbdav
COPY host ./host
COPY host_actions ./host_actions
COPY catalog ./catalog
COPY watchstate ./watchstate
COPY queue_app ./queue_app
COPY cli ./cli

COPY ui ./ui

# Collect static files for whitenoise to serve in production. Django management
# commands only need SOME non-empty SECRET_KEY to load settings; the REAL
# CONTROL_PANEL_SECRET_KEY is injected at runtime via compose `environment:`
# (docker-compose.yml line 478), overriding anything here. The key is set as a
# shell-scoped env var for this single RUN only, so it is NOT baked into an image
# ENV/ARG layer where anyone with `docker inspect` could read it (avd-0031).
RUN CONTROL_PANEL_SECRET_KEY=build-time-collectstatic-dummy \
    python manage.py collectstatic --noinput

EXPOSE 8420

# Serve via gunicorn (multi-worker WSGI) instead of Django's runserver, which
# is single-threaded and documented as unsuitable for production. 2 workers x 4
# threads balances concurrency against SQLite write-lock pressure (the panel is
# a low-traffic, single-operator app; see improvement item 40). Access logs go
# to stdout so promtail/Loki can collect them.
CMD ["gunicorn", "config.wsgi:application", \
     "--bind", "0.0.0.0:8420", \
     "--workers", "2", \
     "--threads", "4", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
