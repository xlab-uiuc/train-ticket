ARG JAVA_RUNTIME_IMAGE=ghcr.io/sregym/train-ticket-java-runtime:otel-2.31.1@sha256:fe4dfdd81f7479b68a2bdb594cc5170cad9a5872a11481bb3946f78a95844136
FROM ${JAVA_RUNTIME_IMAGE}

ENV OTEL_SERVICE_NAME=ts-delivery-service

RUN /bin/cp /usr/share/zoneinfo/Asia/Shanghai /etc/localtime && echo 'Asia/Shanghai' >/etc/timezone

ADD ./target/ts-delivery-service-1.0.jar /app/
CMD ["java", "-Xmx200m",  "-jar", "/app/ts-delivery-service-1.0.jar"]

EXPOSE 18856
