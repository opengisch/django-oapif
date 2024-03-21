FROM python:3.10-buster AS prod

WORKDIR /usr/src/app

# set environment variables
ENV PYTHONUNBUFFERED 1

# install dependencies
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y \
    libproj-dev \
    gdal-bin \
    gettext \
    graphviz

COPY ./requirements.txt .
RUN pip install -r requirements.txt

COPY /src /usr/src/app


FROM prod as dev

ENV PYTHONDONTWRITEBYTECODE 1
COPY ./requirements-dev.txt .
pip install -r requirements-dev.txt
