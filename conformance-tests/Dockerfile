# Courtesy of https://github.com/opengeospatial/ets-ogcapi-features10/issues/197

FROM maven:3.8-openjdk-18

# Copy actual source files
ARG VERSION=1.4
RUN git clone --depth 1 --branch ${VERSION} https://github.com/opengeospatial/ets-ogcapi-features10.git /build

WORKDIR /build/

# COPY pom.xml .  # checkedout already

RUN mvn --version

# Pre-download all dependencies to increase caching in docker builds
RUN mvn dependency:resolve dependency:resolve-plugins dependency:copy-dependencies dependency:go-offline -Pdocker

# Copy actual source files
# COPY ./src ./src  # checkedout already

# Install offline to avoid triggering new dependency update
RUN mvn install -DskipTests -Dmaven.javadoc.skip

# TODO: Should get the version from build context
# ARG VERSION=1.5-SNAPSHOT  # done above
ARG OUTPUT_DIR=/build/run/output
ARG TEST_RUN_PROPS=/build/run/test-run-props.xml

ENV VERSION=${VERSION}
ENV OUTPUT_DIR=${OUTPUT_DIR}
ENV TEST_RUN_PROPS=${TEST_RUN_PROPS}

ADD ./test-run-props.xml /build/run/test-run-props.xml

ENTRYPOINT [ "sh", "-c" ]
CMD ["java -jar /build/target/ets-ogcapi-features10-${VERSION}-aio.jar -o /tmp/test_ouputs/ -h true ${TEST_RUN_PROPS} && find /tmp/test_ouputs/ -iname 'emailable-report.html' -exec mv '{}' ${OUTPUT_DIR} \\;"]
