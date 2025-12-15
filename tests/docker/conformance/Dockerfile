FROM pdok/ets-ogcapi-features10-docker:latest AS prebuilt

FROM maven:3.9-eclipse-temurin-25

COPY --from=prebuilt /opt/ets-ogcapi-features10-aio.jar /opt/ets-ogcapi-features10-aio.jar

WORKDIR /build/

CMD ["sh", "-c", "/build/run/run.sh"]
