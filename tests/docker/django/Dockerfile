FROM python:3.12-bookworm


# set environment variables
ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1

# install dependencies
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y \
    libproj-dev \
    gdal-bin \
    gettext \
    graphviz

COPY . /usr/src/

RUN pip install /usr/src/.[dev]

WORKDIR /usr/src/tests
