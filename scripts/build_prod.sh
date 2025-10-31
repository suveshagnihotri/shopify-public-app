#!/usr/bin/env bash
set -euo pipefail

echo "==> Building production Docker images"
docker-compose -f docker-compose.prod.yml build

echo "==> Build complete!"

