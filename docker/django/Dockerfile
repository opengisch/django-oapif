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
    gettext \
    graphviz

# install dependencies
COPY ./requirements.txt .
RUN pip install -r requirements.txt

# install dev depenencies
ARG DEV=false
COPY ./requirements-dev.txt .
RUN if [ "$DEV" = "true" ] ; then pip install -r requirements-dev.txt ; fi

# copy project
COPY /src /usr/src/app
