# pull official base image
FROM python:3.10-buster

# set work directory
WORKDIR /usr/src/app

# set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# install dependencies
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y \
    libproj-dev \
    gdal-bin \
    gettext \
    graphviz

# install dependencies
COPY ./requirements.txt .
RUN pip install -r requirements.txt

# install dev dependencies
ARG DEV=false
COPY ./requirements-dev.txt .
RUN if [ "$DEV" = "true" ] ; then pip install -r requirements-dev.txt ; fi

# copy project
COPY /src /usr/src/app

# download fixtures
RUN curl -L -o /usr/src/app/tests/fixtures/polygon_2056_10fields.json.gz 'https://drive.google.com/uc?export=download&id=1DhCDaDAA3YvZIP9XFHiap5wjeCCWIfRU'
RUN cp /usr/src/app/tests/fixtures/polygon_2056_10fields.json.gz /usr/src/app/tests/fixtures/polygon_2056_10fields_local_geom.json.gz
