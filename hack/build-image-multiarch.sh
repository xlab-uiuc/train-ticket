#!/usr/bin/env bash
set -eu

REPO="${1:-ghcr.io/sregym}"
TAG="${2:-latest}"
PLATFORMS="linux/amd64,linux/arm64"

echo ""
echo "=== Multi-arch image build ==="
echo "Repo: $REPO, Tag: $TAG"
echo "Platforms: $PLATFORMS"
echo ""

# Ensure buildx builder exists
if ! docker buildx inspect multiarch > /dev/null 2>&1; then
  echo "Creating buildx builder 'multiarch'..."
  docker buildx create --name multiarch --driver docker-container --use
  docker buildx inspect --bootstrap
else
  docker buildx use multiarch
fi

FAILED=""
SUCCESS=0

for dir in ts-*; do
  if [[ -d "$dir" ]] && [[ -f "$dir/Dockerfile" ]]; then
    echo ""
    echo "=== Building $dir ==="
    if docker buildx build \
      --platform "$PLATFORMS" \
      -t "$REPO/${dir}:${TAG}" \
      --push \
      "$dir"; then
      SUCCESS=$((SUCCESS + 1))
    else
      echo "FAILED: $dir"
      FAILED="$FAILED $dir"
    fi
  fi
done

echo ""
echo "=== Build Summary ==="
echo "Success: $SUCCESS"
if [ -n "$FAILED" ]; then
  echo "Failed:$FAILED"
else
  echo "Failed: none"
fi
