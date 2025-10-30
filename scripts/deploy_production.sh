#!/usr/bin/env bash
set -euo pipefail

# Configuration
DOMAIN=${DOMAIN:-peeq.co.in}
EMAIL=${EMAIL:-admin@${DOMAIN}}
PROJECT_DIR=${PROJECT_DIR:-/home/ubuntu/shopify_public_app}
GIT_URL=${GIT_URL:-}
BRANCH=${BRANCH:-main}
NGINX_SITE=/etc/nginx/sites-available/${DOMAIN}
NGINX_LINK=/etc/nginx/sites-enabled/${DOMAIN}

echo "==> Starting production deployment for ${DOMAIN}"

if [[ ! -d ${PROJECT_DIR} ]]; then
  if [[ -n "${GIT_URL}" ]]; then
    echo "==> PROJECT_DIR not found. Cloning ${GIT_URL} into ${PROJECT_DIR}"
    sudo mkdir -p "${PROJECT_DIR}"
    sudo chown -R "$USER":"$USER" "${PROJECT_DIR}"
    git clone --branch "${BRANCH}" "${GIT_URL}" "${PROJECT_DIR}"
  else
    echo "==> PROJECT_DIR not found and GIT_URL not provided. Using current directory $(pwd) as PROJECT_DIR."
    PROJECT_DIR=$(pwd)
  fi
fi

cd "${PROJECT_DIR}"

echo "==> Installing base packages"
sudo apt-get update -y
sudo apt-get install -y nginx snapd

echo "==> Installing Docker & Compose"
if ! command -v docker >/dev/null 2>&1; then
  sudo apt-get install -y ca-certificates curl gnupg
  sudo install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
  sudo apt-get update -y
  sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  sudo usermod -aG docker $USER || true
fi

echo "==> Ensuring .env exists"
if [[ ! -f .env ]]; then
  cp env.example .env
fi

echo "==> Setting APP_URL, PUBLIC_URL, and REDIRECT in .env"
sed -i "s|^APP_URL=.*|APP_URL=https://${DOMAIN}|" .env || true
sed -i "s|^PUBLIC_URL=.*|PUBLIC_URL=https://${DOMAIN}|" .env || true
sed -i "s|^SHOPIFY_REDIRECT_URI=.*|SHOPIFY_REDIRECT_URI=https://${DOMAIN}/auth/callback|" .env || true

echo "==> Deploying Nginx site"
sudo cp ${PROJECT_DIR}/nginx/peeq.conf ${NGINX_SITE}
sudo sed -i "s/peeq.co.in/${DOMAIN}/g" ${NGINX_SITE}
sudo ln -sf ${NGINX_SITE} ${NGINX_LINK}
sudo nginx -t
sudo systemctl restart nginx

echo "==> Starting Docker services"
docker compose pull || true
docker compose up -d --build

echo "==> Installing Certbot and issuing certificate"
sudo snap install core || true
sudo snap refresh core || true
sudo snap install --classic certbot || true
sudo ln -sf /snap/bin/certbot /usr/bin/certbot
sudo certbot --nginx -d ${DOMAIN} -d www.${DOMAIN} --non-interactive --agree-tos -m ${EMAIL} || true

echo "==> Creating systemd unit for docker compose"
sudo tee /etc/systemd/system/shopify-app.service >/dev/null <<UNIT
[Unit]
Description=Shopify Public App (Docker Compose)
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
WorkingDirectory=${PROJECT_DIR}
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
UNIT

sudo systemctl daemon-reload
sudo systemctl enable shopify-app
sudo systemctl restart shopify-app

echo "==> Deployment completed. Visit: https://${DOMAIN}"

