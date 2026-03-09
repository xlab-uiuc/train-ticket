#!/usr/bin/env bash
# Build all 47 images (46 services + deploy-job) as multi-arch and push to ghcr.io/sregym
set -eu

REPO="${1:-ghcr.io/sregym}"
TAG="${2:-latest}"
PLATFORMS="linux/amd64,linux/arm64"
JAVA_HOME="/usr/lib/jvm/java-8-openjdk-amd64"
export JAVA_HOME

LOGFILE="hack/build-multiarch-$(date +%Y%m%d-%H%M%S).log"

# Tee all output to logfile and stdout, strip ANSI codes from logfile
# exec > >(tee >(sed 's/\x1b\[[0-9;]*m//g' >> "$LOGFILE")) 2>&1
# echo "Logging to $LOGFILE"

# Java services (need Maven build)
JAVA_SERVICES=(
  ts-admin-basic-info-service
  ts-admin-order-service
  ts-admin-route-service
  ts-admin-travel-service
  ts-admin-user-service
  ts-assurance-service
  ts-auth-service
  ts-basic-service
  ts-cancel-service
  ts-config-service
  ts-consign-price-service
  ts-consign-service
  ts-contacts-service
  ts-delivery-service
  ts-execute-service
  ts-food-delivery-service
  ts-food-service
  ts-gateway-service
  ts-inside-payment-service
  ts-notification-service
  ts-order-other-service
  ts-order-service
  ts-payment-service
  ts-preserve-other-service
  ts-preserve-service
  ts-price-service
  ts-rebook-service
  ts-route-plan-service
  ts-route-service
  ts-seat-service
  ts-security-service
  ts-station-food-service
  ts-station-service
  ts-train-food-service
  ts-train-service
  ts-travel-plan-service
  ts-travel-service
  ts-travel2-service
  ts-user-service
  ts-verification-code-service
  ts-wait-order-service
)

# Non-Java services (just Docker build, no Maven)
NON_JAVA_SERVICES=(
  ts-avatar-service
  ts-news-service
  ts-ticket-office-service
  ts-ui-dashboard
  ts-voucher-service
)

ALL_SERVICES=("${JAVA_SERVICES[@]}" "${NON_JAVA_SERVICES[@]}")
TOTAL=$(( ${#ALL_SERVICES[@]} + 1 ))  # +1 for deploy-job

echo "========================================"
echo "  Multi-arch build -> $REPO"
echo "  Tag: $TAG"
echo "  Platforms: $PLATFORMS"
echo "  Total images: $TOTAL"
echo "========================================"
echo ""

# Ensure buildx builder exists
if ! docker buildx inspect multiarch > /dev/null 2>&1; then
  echo "Creating buildx builder 'multiarch'..."
  docker buildx create --name multiarch --driver docker-container --use
  docker buildx inspect --bootstrap
else
  docker buildx use multiarch
fi

FAILED=()
OK=0
START_TIME=$(date +%s)

# Step 1: Maven build for Java services
echo "=== Maven: building ts-common ==="
mvn clean install -DskipTests -N
mvn clean install -DskipTests -f ts-common/pom.xml

for svc in "${JAVA_SERVICES[@]}"; do
  echo "=== Maven: $svc ==="
  mvn clean package -DskipTests -f "$svc/pom.xml"
done
echo ""

# Step 2: Docker buildx for all services
IDX=0
for svc in "${ALL_SERVICES[@]}"; do
  IDX=$((IDX + 1))
  PCT=$(( (IDX - 1) * 100 / TOTAL ))
  echo "[$IDX/$TOTAL] ($PCT%) $svc"
  if docker buildx build --platform "$PLATFORMS" \
    -t "$REPO/$svc:$TAG" --push "$svc/"; then
    OK=$((OK + 1))
    ELAPSED=$(( $(date +%s) - START_TIME ))
    ETA=$(( ELAPSED * (TOTAL - IDX) / IDX ))
    echo "  done (elapsed: ${ELAPSED}s, eta: ~${ETA}s)"
  else
    echo "  FAILED: $svc"
    FAILED+=("$svc")
  fi
  echo ""
done

# Step 3: deploy-job
IDX=$((IDX + 1))
PCT=$(( (IDX - 1) * 100 / TOTAL ))
echo "[$IDX/$TOTAL] ($PCT%) train-ticket-deploy"
if docker buildx build --platform "$PLATFORMS" \
  -t "$REPO/train-ticket-deploy:$TAG" --push deploy-job/; then
  OK=$((OK + 1))
else
  echo "  FAILED: train-ticket-deploy"
  FAILED+=("train-ticket-deploy")
fi

ELAPSED=$(( $(date +%s) - START_TIME ))
MINS=$(( ELAPSED / 60 ))
SECS=$(( ELAPSED % 60 ))

echo ""
echo "========================================"
echo "  COMPLETE"
echo "  OK:     $OK / $TOTAL"
echo "  Failed: ${#FAILED[@]} / $TOTAL"
echo "  Time:   ${MINS}m ${SECS}s"
echo "========================================"

if [ ${#FAILED[@]} -gt 0 ]; then
  echo ""
  echo "Failed images:"
  for f in "${FAILED[@]}"; do
    echo "  - $f"
  done
fi
