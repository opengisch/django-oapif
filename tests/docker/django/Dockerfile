# the image to build on: bookworm brings GEOS 3.11, trixie the 3.13 that curves need
ARG PYTHON_IMAGE=python:3.12-bookworm
FROM ${PYTHON_IMAGE}


# set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# install dependencies
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y \
    libproj-dev \
    gdal-bin \
    gettext \
    graphviz

COPY requirements.txt .
COPY requirements-dev.txt .
COPY requirements-arrow.txt .

RUN pip install -r requirements.txt
RUN pip install -r requirements-dev.txt
RUN pip install -r requirements-arrow.txt

COPY . /usr/src/

RUN pip install --editable /usr/src/.[dev]

# a Django to install over the released one, such as a fork that knows curves; last, as installing
# the package would otherwise put the released one back
ARG DJANGO_REQUIREMENT=""
RUN if [ -n "$DJANGO_REQUIREMENT" ]; then pip install --force-reinstall --no-deps "$DJANGO_REQUIREMENT"; fi

WORKDIR /usr/src/tests
