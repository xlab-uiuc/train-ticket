ARG JAVA_RUNTIME_IMAGE=ghcr.io/sregym/train-ticket-java-runtime:otel-2.31.1@sha256:fe4dfdd81f7479b68a2bdb594cc5170cad9a5872a11481bb3946f78a95844136
FROM ${JAVA_RUNTIME_IMAGE}

ENV OTEL_SERVICE_NAME=ts-inside-payment-service

LABEL maintainer="TrainTicket F1 Fault Injection"

WORKDIR /app

COPY target/ts-inside-payment-service-1.0.jar app.jar

EXPOSE 18673

ENTRYPOINT ["java", "-jar", "app.jar"]
