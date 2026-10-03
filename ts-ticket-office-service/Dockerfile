FROM node:22-bookworm

RUN /bin/cp /usr/share/zoneinfo/Asia/Shanghai /etc/localtime && echo 'Asia/Shanghai' >/etc/timezone

RUN mkdir -p /app
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --omit=dev --ignore-scripts
ADD ./public /app/public

ADD ./bin /app/bin
ADD ./app.js /app/
ENV NODE_OPTIONS="--require @opentelemetry/auto-instrumentations-node/register" \
    OTEL_SERVICE_NAME=ts-ticket-office-service \
    OTEL_EXPORTER_OTLP_PROTOCOL=grpc \
    OTEL_METRICS_EXPORTER=none \
    OTEL_LOGS_EXPORTER=none \
    OTEL_NODE_ENABLED_INSTRUMENTATIONS=http,express,mysql \
    OTEL_NODE_RESOURCE_DETECTORS=env,process

CMD [ "node", "bin/www" ]

EXPOSE 16108
