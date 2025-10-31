#!/usr/bin/env bash
set -euo pipefail

echo "==> Building production Docker images"
# Disable buildx to use legacy builder (required for buildx < 0.17)
DOCKER_BUILDKIT=0 docker-compose -f docker-compose.prod.yml build

echo "==> Build complete!"

