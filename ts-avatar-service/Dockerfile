FROM python:3.9-bookworm

RUN /bin/cp /usr/share/zoneinfo/Asia/Shanghai /etc/localtime && echo 'Asia/Shanghai' >/etc/timezone

RUN apt update -y
RUN apt install -y cmake
RUN apt install -y libgl1

# Pin to an older version that works with dlib 19.24.2
ENV CMAKE_POLICY_VERSION_MINIMUM=3.5
ENV PYTHONUNBUFFERED=TRUE

RUN mkdir -p /app
ADD . /app/
WORKDIR /app

RUN pip install -r requirements.txt

ENV OTEL_SERVICE_NAME=ts-avatar-service \
    OTEL_EXPORTER_OTLP_PROTOCOL=grpc \
    OTEL_METRICS_EXPORTER=none \
    OTEL_LOGS_EXPORTER=none

CMD ["opentelemetry-instrument", "gunicorn", "-w", "4", "-b", "0.0.0.0:17001", "app:app"]

EXPOSE 17001
