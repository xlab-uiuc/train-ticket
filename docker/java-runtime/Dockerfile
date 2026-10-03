FROM eclipse-temurin:8-jre

ADD --checksum=sha256:bbf83c151b6400709e2f225bdd07a04f839d9d13b8b93464241333fd25d3e3ba \
    https://github.com/open-telemetry/opentelemetry-java-instrumentation/releases/download/v2.31.1/opentelemetry-javaagent.jar \
    /opt/otel/opentelemetry-javaagent.jar

ENV JAVA_TOOL_OPTIONS="-javaagent:/opt/otel/opentelemetry-javaagent.jar" \
    OTEL_EXPORTER_OTLP_PROTOCOL=grpc \
    OTEL_METRICS_EXPORTER=none \
    OTEL_LOGS_EXPORTER=none
