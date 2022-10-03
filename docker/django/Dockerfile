# pull official base image
FROM python:3.9-buster

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
    gettext

# install dependencies
COPY ./requirements.txt .
RUN pip install -r requirements.txt

# copy project
COPY /signalo /usr/src/app

# setup entrypoint
COPY ./docker/django/entrypoint.sh /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
