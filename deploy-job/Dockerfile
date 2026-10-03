FROM ghcr.io/sregym/train-ticket-deploy:20260913.2@sha256:84a2b504ae7cc5b1f9095d6227f2ba6b34a2c7a704e2df1d8ba33bc60edfa6db

WORKDIR /usr/local/bin/

COPY deploy.sh /usr/local/bin/
COPY deployment /usr/local/bin/deployment

ARG IMAGE_REGISTRY=ghcr.io/sregym
ARG SERVICE_IMAGE_TAG=latest
RUN chmod +x /usr/local/bin/deploy.sh && \
    sed -i "s|ghcr.io/sregym/\(ts-[a-z0-9-]*\):latest|${IMAGE_REGISTRY}/\1:${SERVICE_IMAGE_TAG}|g" \
      deployment/kubernetes-manifests/quickstart-k8s/yamls/deploy.yaml.sample

ENTRYPOINT ["/bin/bash", "-c", "/usr/local/bin/deploy.sh ${NAMESPACE}"]
