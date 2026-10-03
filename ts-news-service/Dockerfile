FROM --platform=$BUILDPLATFORM golang:1.23-bookworm AS builder

WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY ./src/main ./

ARG TARGETOS
ARG TARGETARCH
RUN CGO_ENABLED=0 GOOS=$TARGETOS GOARCH=$TARGETARCH go build -o app .

FROM alpine:3.19
RUN apk add --no-cache tzdata && \
    cp /usr/share/zoneinfo/Asia/Shanghai /etc/localtime && \
    echo 'Asia/Shanghai' > /etc/timezone

WORKDIR /app
COPY --from=builder /app/app .
ENV OTEL_SERVICE_NAME=ts-news-service \
    OTEL_EXPORTER_OTLP_PROTOCOL=grpc
CMD ["./app"]
EXPOSE 12862
