#!/usr/bin/env bash
mkdir django-ogcapif
cp -r src/django_oapif django-ogcapif/django_ogcapif/
cp pyproject.toml LICENSE README.md requirements.txt requirements-dev.txt \
    django-ogcapif/
python -m build django-ogcapif/
