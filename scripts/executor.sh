#!/usr/bin/env bash
set -euo pipefail

# Unified executor for local and production tasks
# Usage examples:
#   ./scripts/executor.sh app              # run Flask app locally
#   ./scripts/executor.sh worker           # run Celery worker locally
#   ./scripts/executor.sh up               # docker compose up (prod file optional)
#   ./scripts/executor.sh down             # docker compose down
#   ./scripts/executor.sh logs nginx       # docker logs for a service
#   ./scripts/executor.sh certbot peeq.co.in you@peeq.co.in  # issue certs via dockerized certbot

PROJECT_DIR=${PROJECT_DIR:-$(cd "$(dirname "$0")/.." && pwd)}
COMPOSE_FILE=${COMPOSE_FILE:-docker-compose.yml}
COMPOSE_FILE_PROD=${COMPOSE_FILE_PROD:-docker-compose.prod.yml}
PY=${PY:-python3}

cd "$PROJECT_DIR"

ensure_compose() {
  if command -v docker >/dev/null 2>&1; then
    if docker compose version >/dev/null 2>&1; then
      echo "docker compose"
      return 0
    fi
  fi
  if command -v docker-compose >/dev/null 2>&1; then
    echo "docker-compose"
    return 0
  fi
  echo "ERROR: docker compose not found" >&2
  exit 1
}

case "${1:-}" in
  app)
    export FLASK_ENV=${FLASK_ENV:-development}
    export DATABASE_URL=${DATABASE_URL:-postgresql://postgres:password@localhost:5432/shopify_app_db}
    exec ${PY} app.py
    ;;
  worker)
    export REDIS_URL=${REDIS_URL:-redis://localhost:6379/0}
    exec celery -A celery_app worker --loglevel=info
    ;;
  beat)
    exec celery -A celery_app beat --loglevel=info
    ;;
  migrate)
    export FLASK_APP=app.py
    flask db migrate -m "${2:-executor migration}" || true
    ;;
  upgrade)
    export FLASK_APP=app.py
    flask db upgrade
    ;;
  up)
    BIN=$(ensure_compose)
    FILE=${2:-$COMPOSE_FILE}
    exec $BIN -f "$FILE" up -d --build
    ;;
  down)
    BIN=$(ensure_compose)
    FILE=${2:-$COMPOSE_FILE}
    exec $BIN -f "$FILE" down
    ;;
  restart)
    BIN=$(ensure_compose)
    FILE=${2:-$COMPOSE_FILE}
    exec $BIN -f "$FILE" restart
    ;;
  logs)
    BIN=$(ensure_compose)
    FILE=${3:-$COMPOSE_FILE}
    SERVICE=${2:-app}
    exec $BIN -f "$FILE" logs -f "$SERVICE"
    ;;
  certbot)
    DOMAIN=${2:-}
    EMAIL=${3:-}
    if [[ -z "$DOMAIN" || -z "$EMAIL" ]]; then
      echo "Usage: $0 certbot <domain> <email> [compose_file]" >&2
      exit 1
    fi
    BIN=$(ensure_compose)
    FILE=${4:-$COMPOSE_FILE_PROD}
    $BIN -f "$FILE" run --rm certbot certbot certonly \
      --webroot -w /var/www/certbot \
      -d "$DOMAIN" -d "www.$DOMAIN" \
      --email "$EMAIL" --agree-tos --no-eff-email
    exec $BIN -f "$FILE" restart nginx
    ;;
  nginx-reload)
    BIN=$(ensure_compose)
    FILE=${2:-$COMPOSE_FILE_PROD}
    $BIN -f "$FILE" exec nginx nginx -t
    exec $BIN -f "$FILE" restart nginx
    ;;
  *)
    cat <<USAGE
Usage: $0 <command> [args]
Commands:
  app                         Run Flask app locally
  worker                      Run Celery worker locally
  beat                        Run Celery beat locally
  migrate [msg]               Create a DB migration
  upgrade                     Apply DB migrations
  up [compose.yml]            docker compose up -d --build
  down [compose.yml]          docker compose down
  restart [compose.yml]       docker compose restart
  logs <service> [compose]    Tail docker logs for service
  certbot <domain> <email>    Issue/renew certs using dockerized certbot (prod compose)
  nginx-reload [compose]      Validate and reload nginx container
USAGE
    exit 1
    ;;
 esac
