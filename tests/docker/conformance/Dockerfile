# Courtesy of https://github.com/opengeospatial/ets-ogcapi-features10/issues/197

FROM maven:3.9-eclipse-temurin-25

# Copy actual source files
ARG VERSION=1.10
RUN git clone --depth 1 --branch ${VERSION} https://github.com/opengeospatial/ets-ogcapi-features10.git /build

WORKDIR /build/

RUN mvn --version

# Pre-download all dependencies to increase caching in docker builds
RUN mvn dependency:resolve dependency:resolve-plugins dependency:copy-dependencies dependency:go-offline -Pdocker

# Install offline to avoid triggering new dependency update
RUN mvn install -DskipTests -Dmaven.javadoc.skip

ENV VERSION=${VERSION}

CMD ["sh", "-c", "/build/run/run.sh"]
