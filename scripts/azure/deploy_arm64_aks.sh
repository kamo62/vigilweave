#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
ENV_FILE="${1:-$ROOT_DIR/infra/azure/arm64-aks/.env.generated}"
K8S_DIR="$ROOT_DIR/infra/azure/arm64-aks/k8s"

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    printf 'Missing required command: %s\n' "$1" >&2
    exit 1
  }
}

need_cmd az
need_cmd kubectl
need_cmd docker
need_cmd bun
need_cmd python3
need_cmd openssl

ACCOUNT_JSON="$(az account show -o json)"
SUBSCRIPTION_ID="$(python3 - <<'PY' "$ACCOUNT_JSON"
import json, sys
print(json.loads(sys.argv[1])["id"])
PY
)"
SUBSCRIPTION_HASH="$(printf '%s' "$SUBSCRIPTION_ID" | tr -d '-' | cut -c1-8)"

if [ ! -f "$ENV_FILE" ]; then
  mkdir -p "$(dirname "$ENV_FILE")"
  cat > "$ENV_FILE" <<EOF
RESOURCE_GROUP=rg-vigilweave-ne
LOCATION=northeurope
ROOT_DOMAIN=vigilweave.com
APP_SUBDOMAIN=app
API_SUBDOMAIN=api
LICENSE_SUBDOMAIN=license
MARKETING_STORAGE_ACCOUNT=vw${SUBSCRIPTION_HASH}web
ACR_NAME=vw${SUBSCRIPTION_HASH}acr
AKS_CLUSTER_NAME=aks-vigilweave-ne
AKS_NODE_VM_SIZE=Standard_D4ps_v6
AKS_NODE_COUNT=1
AKS_NODE_OS_DISK_SIZE=128
AKS_KUBERNETES_VERSION=
POSTGRES_SERVER_NAME=vw${SUBSCRIPTION_HASH}pg
POSTGRES_DB_NAME=vigilweave
POSTGRES_LICENSE_DB_NAME=vigilweave_license
POSTGRES_ADMIN_USER=vwadmin
POSTGRES_ADMIN_PASSWORD=$(openssl rand -base64 24 | tr -d '\n' | tr '/' '_' | tr '+' '-')
POSTGRES_SKU=Standard_B1ms
POSTGRES_TIER=Burstable
POSTGRES_STORAGE_GB=32
REDIS_NAME=vw${SUBSCRIPTION_HASH}redis
REDIS_SKU=Basic
REDIS_SIZE=c0
SESSION_SECRET=$(openssl rand -hex 32)
TOKEN_ENCRYPTION_KEY=$(openssl rand -hex 32)
LICENSE_SERVER_SHARED_SECRET=$(openssl rand -hex 32)
LICENSE_SERVER_SESSION_SECRET=$(openssl rand -hex 32)
LICENSE_SERVER_CONFIG_ENCRYPTION_KEY=$(openssl rand -hex 32)
LICENSE_SERVER_OFFLINE_SIGNING_SECRET=$(openssl rand -hex 32)
WORKOS_COOKIE_DOMAIN=.vigilweave.com
WORKOS_API_KEY=
WORKOS_CLIENT_ID=
WORKOS_REDIRECT_URI=https://api.vigilweave.com/api/v1/auth/callback
WORKOS_SESSION_SECRET=
SESSION_AUTH_PROVIDER=local
API_KEYS_ENABLED=true
SAAS_ENABLED=false
LICENSE_TESTING_MODE=false
CELERY_CONCURRENCY=1
WORKER_REPLICAS=1
LICENSE_SERVER_REPLICAS=1
TOOLCHAIN_PROFILE=base
PADDLE_ENVIRONMENT=sandbox
PADDLE_CLIENT_TOKEN=
PADDLE_API_KEY=
PADDLE_WEBHOOK_SECRET=
PADDLE_PRICE_ID_PRO=
PADDLE_PRICE_ID_ENTERPRISE=
PADDLE_PRICE_ID_SELF_HOSTED_PRO=
PADDLE_PRICE_ID_SELF_HOSTED_ENTERPRISE=
IMAGE_TAG=$(date +%Y%m%d%H%M%S)
EOF
  printf 'Created %s with generated defaults. Review it before rerunning if needed.\n' "$ENV_FILE"
fi

set -a
. "$ENV_FILE"
set +a

LICENSE_SUBDOMAIN="${LICENSE_SUBDOMAIN:-license}"
POSTGRES_LICENSE_DB_NAME="${POSTGRES_LICENSE_DB_NAME:-vigilweave_license}"
LICENSE_SERVER_SHARED_SECRET="${LICENSE_SERVER_SHARED_SECRET:-$(openssl rand -hex 32)}"
LICENSE_SERVER_SESSION_SECRET="${LICENSE_SERVER_SESSION_SECRET:-$(openssl rand -hex 32)}"
LICENSE_SERVER_CONFIG_ENCRYPTION_KEY="${LICENSE_SERVER_CONFIG_ENCRYPTION_KEY:-$(openssl rand -hex 32)}"
LICENSE_SERVER_OFFLINE_SIGNING_SECRET="${LICENSE_SERVER_OFFLINE_SIGNING_SECRET:-$(openssl rand -hex 32)}"
LICENSE_SERVER_REPLICAS="${LICENSE_SERVER_REPLICAS:-1}"
PADDLE_ENVIRONMENT="${PADDLE_ENVIRONMENT:-sandbox}"
PADDLE_CLIENT_TOKEN="${PADDLE_CLIENT_TOKEN:-}"
PADDLE_API_KEY="${PADDLE_API_KEY:-}"
PADDLE_WEBHOOK_SECRET="${PADDLE_WEBHOOK_SECRET:-}"
PADDLE_PRICE_ID_PRO="${PADDLE_PRICE_ID_PRO:-}"
PADDLE_PRICE_ID_ENTERPRISE="${PADDLE_PRICE_ID_ENTERPRISE:-}"
PADDLE_PRICE_ID_SELF_HOSTED_PRO="${PADDLE_PRICE_ID_SELF_HOSTED_PRO:-}"
PADDLE_PRICE_ID_SELF_HOSTED_ENTERPRISE="${PADDLE_PRICE_ID_SELF_HOSTED_ENTERPRISE:-}"

APP_DOMAIN="${APP_SUBDOMAIN}.${ROOT_DOMAIN}"
API_DOMAIN="${API_SUBDOMAIN}.${ROOT_DOMAIN}"
LICENSE_DOMAIN="${LICENSE_SUBDOMAIN}.${ROOT_DOMAIN}"
MARKETING_DOMAIN="${MARKETING_DOMAIN:-https://${ROOT_DOMAIN}}"
VIGILWEAVE_WEB_BASE_URL="https://${APP_DOMAIN}"
VIGILWEAVE_API_BASE_URL="https://${API_DOMAIN}"
LICENSE_SERVER_API_BASE_URL="${LICENSE_SERVER_API_BASE_URL:-http://license-server}"
LICENSE_SERVER_URL="${LICENSE_SERVER_URL:-${LICENSE_SERVER_API_BASE_URL}/v1/verify}"
LICENSE_SERVER_ALLOWED_ORIGINS="${LICENSE_SERVER_ALLOWED_ORIGINS:-[\"https://${LICENSE_DOMAIN}\"]}"
WORKOS_REDIRECT_URI="https://${API_DOMAIN}/api/v1/auth/callback"

az group create --name "$RESOURCE_GROUP" --location "$LOCATION" --output none

if ! az acr show --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" >/dev/null 2>&1; then
  az acr create \
    --name "$ACR_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --location "$LOCATION" \
    --sku Basic \
    --admin-enabled false \
    --output none
fi

if ! az storage account show --name "$MARKETING_STORAGE_ACCOUNT" --resource-group "$RESOURCE_GROUP" >/dev/null 2>&1; then
  az storage account create \
    --name "$MARKETING_STORAGE_ACCOUNT" \
    --resource-group "$RESOURCE_GROUP" \
    --location "$LOCATION" \
    --sku Standard_LRS \
    --kind StorageV2 \
    --https-only true \
    --min-tls-version TLS1_2 \
    --allow-blob-public-access false \
    --output none
fi
az storage blob service-properties update \
  --account-name "$MARKETING_STORAGE_ACCOUNT" \
  --static-website \
  --index-document index.html \
  --404-document index.html \
  --auth-mode login \
  --output none

if ! az postgres flexible-server show --name "$POSTGRES_SERVER_NAME" --resource-group "$RESOURCE_GROUP" >/dev/null 2>&1; then
  az postgres flexible-server create \
    --resource-group "$RESOURCE_GROUP" \
    --location "$LOCATION" \
    --name "$POSTGRES_SERVER_NAME" \
    --admin-user "$POSTGRES_ADMIN_USER" \
    --admin-password "$POSTGRES_ADMIN_PASSWORD" \
    --sku-name "$POSTGRES_SKU" \
    --tier "$POSTGRES_TIER" \
    --storage-size "$POSTGRES_STORAGE_GB" \
    --public-access 0.0.0.0 \
    --version 17 \
    --yes \
    --output none
fi

az postgres flexible-server db create \
  --resource-group "$RESOURCE_GROUP" \
  --server-name "$POSTGRES_SERVER_NAME" \
  --database-name "$POSTGRES_DB_NAME" \
  --output none >/dev/null 2>&1 || true

az postgres flexible-server db create \
  --resource-group "$RESOURCE_GROUP" \
  --server-name "$POSTGRES_SERVER_NAME" \
  --database-name "$POSTGRES_LICENSE_DB_NAME" \
  --output none >/dev/null 2>&1 || true

if ! az redis show --name "$REDIS_NAME" --resource-group "$RESOURCE_GROUP" >/dev/null 2>&1; then
  az redis create \
    --name "$REDIS_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --location "$LOCATION" \
    --sku "$REDIS_SKU" \
    --vm-size "$REDIS_SIZE" \
    --minimum-tls-version 1.2 \
    --redis-version 6 \
    --output none
fi

ACR_ID="$(az acr show --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" --query id -o tsv)"
ACR_LOGIN_SERVER="$(az acr show --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" --query loginServer -o tsv)"

if ! az aks show --name "$AKS_CLUSTER_NAME" --resource-group "$RESOURCE_GROUP" >/dev/null 2>&1; then
  AKS_CREATE_ARGS=(
    --resource-group "$RESOURCE_GROUP"
    --name "$AKS_CLUSTER_NAME"
    --location "$LOCATION"
    --tier free
    --node-vm-size "$AKS_NODE_VM_SIZE"
    --node-count "$AKS_NODE_COUNT"
    --node-osdisk-size "$AKS_NODE_OS_DISK_SIZE"
    --os-sku AzureLinux3
    --enable-managed-identity
    --attach-acr "$ACR_ID"
    --generate-ssh-keys
    --network-plugin azure
    --nodepool-name systempool
    --output none
  )
  if [ -n "${AKS_KUBERNETES_VERSION}" ]; then
    AKS_CREATE_ARGS+=(--kubernetes-version "$AKS_KUBERNETES_VERSION")
  fi
  az aks create "${AKS_CREATE_ARGS[@]}"
fi

az aks get-credentials \
  --resource-group "$RESOURCE_GROUP" \
  --name "$AKS_CLUSTER_NAME" \
  --overwrite-existing \
  --output none

az acr login --name "$ACR_NAME"

API_IMAGE="${ACR_LOGIN_SERVER}/vigilweave-api:${IMAGE_TAG}"
LICENSE_SERVER_IMAGE="${ACR_LOGIN_SERVER}/vigilweave-license-server:${IMAGE_TAG}"

docker buildx build \
  --platform linux/arm64 \
  --tag "$API_IMAGE" \
  --push \
  "$ROOT_DIR"

docker buildx build \
  --platform linux/arm64 \
  --tag "$LICENSE_SERVER_IMAGE" \
  --push \
  "$ROOT_DIR/services/license-server"

pushd "$ROOT_DIR/frontend" >/dev/null
  bun install --frozen-lockfile
  VITE_API_BASE_URL="$VIGILWEAVE_API_BASE_URL" \
  VITE_MARKETING_URL="https://${ROOT_DOMAIN}" \
  VITE_APP_URL="$VIGILWEAVE_WEB_BASE_URL" \
  bun run build
popd >/dev/null

STORAGE_ACCOUNT_KEY="$(az storage account keys list --account-name "$MARKETING_STORAGE_ACCOUNT" --resource-group "$RESOURCE_GROUP" --query '[0].value' -o tsv)"

az storage blob upload-batch \
  --account-name "$MARKETING_STORAGE_ACCOUNT" \
  --account-key "$STORAGE_ACCOUNT_KEY" \
  --destination '$web' \
  --source "$ROOT_DIR/frontend/dist" \
  --overwrite \
  --output none

REDIS_HOST="$(az redis show --name "$REDIS_NAME" --resource-group "$RESOURCE_GROUP" --query hostName -o tsv)"
REDIS_KEY="$(az redis list-keys --name "$REDIS_NAME" --resource-group "$RESOURCE_GROUP" --query primaryKey -o tsv)"
POSTGRES_FQDN="$(az postgres flexible-server show --name "$POSTGRES_SERVER_NAME" --resource-group "$RESOURCE_GROUP" --query fullyQualifiedDomainName -o tsv)"
STORAGE_WEB_HOST="$(az storage account show --name "$MARKETING_STORAGE_ACCOUNT" --resource-group "$RESOURCE_GROUP" --query primaryEndpoints.web -o tsv | sed 's#https://##; s#/$##')"

DATABASE_URL="postgresql+psycopg://${POSTGRES_ADMIN_USER}:${POSTGRES_ADMIN_PASSWORD}@${POSTGRES_FQDN}:5432/${POSTGRES_DB_NAME}?sslmode=require"
LICENSE_SERVER_DATABASE_URL="postgresql+psycopg2://${POSTGRES_ADMIN_USER}:${POSTGRES_ADMIN_PASSWORD}@${POSTGRES_FQDN}:5432/${POSTGRES_LICENSE_DB_NAME}?sslmode=require"
REDIS_URL="rediss://:${REDIS_KEY}@${REDIS_HOST}:6380/0?ssl_cert_reqs=required"

kubectl apply -f "$K8S_DIR/namespace.yaml"

kubectl -n vigilweave delete secret vigilweave-secrets --ignore-not-found >/dev/null
kubectl -n vigilweave create secret generic vigilweave-secrets \
  --from-literal=SESSION_SECRET="$SESSION_SECRET" \
  --from-literal=TOKEN_ENCRYPTION_KEY="$TOKEN_ENCRYPTION_KEY" \
  --from-literal=WORKOS_REDIRECT_URI="$WORKOS_REDIRECT_URI" \
  --from-literal=WORKOS_COOKIE_DOMAIN="$WORKOS_COOKIE_DOMAIN" \
  --from-literal=WORKOS_API_KEY="${WORKOS_API_KEY:-}" \
  --from-literal=WORKOS_CLIENT_ID="${WORKOS_CLIENT_ID:-}" \
  --from-literal=WORKOS_SESSION_SECRET="${WORKOS_SESSION_SECRET:-$SESSION_SECRET}" \
  --from-literal=PADDLE_API_KEY="${PADDLE_API_KEY:-}" \
  --from-literal=PADDLE_WEBHOOK_SECRET="${PADDLE_WEBHOOK_SECRET:-}" \
  --from-literal=LICENSE_SERVER_SHARED_SECRET="${LICENSE_SERVER_SHARED_SECRET:-}" >/dev/null

kubectl -n vigilweave delete secret license-server-secrets --ignore-not-found >/dev/null
kubectl -n vigilweave create secret generic license-server-secrets \
  --from-literal=SESSION_SECRET="$LICENSE_SERVER_SESSION_SECRET" \
  --from-literal=CONFIG_ENCRYPTION_KEY="$LICENSE_SERVER_CONFIG_ENCRYPTION_KEY" \
  --from-literal=OFFLINE_SIGNING_SECRET="$LICENSE_SERVER_OFFLINE_SIGNING_SECRET" \
  --from-literal=FULFILLMENT_SHARED_SECRET="$LICENSE_SERVER_SHARED_SECRET" >/dev/null

export DATABASE_URL LICENSE_SERVER_DATABASE_URL REDIS_URL TOOLCHAIN_PROFILE SESSION_AUTH_PROVIDER API_KEYS_ENABLED SAAS_ENABLED
export LICENSE_TESTING_MODE CELERY_CONCURRENCY VIGILWEAVE_WEB_BASE_URL VIGILWEAVE_API_BASE_URL
export MARKETING_DOMAIN WORKOS_COOKIE_DOMAIN API_IMAGE LICENSE_SERVER_IMAGE WORKER_REPLICAS LICENSE_SERVER_REPLICAS API_DOMAIN LICENSE_DOMAIN
export LICENSE_SERVER_URL LICENSE_SERVER_API_BASE_URL LICENSE_SERVER_ALLOWED_ORIGINS
export PADDLE_ENVIRONMENT PADDLE_CLIENT_TOKEN PADDLE_PRICE_ID_PRO PADDLE_PRICE_ID_ENTERPRISE
export PADDLE_PRICE_ID_SELF_HOSTED_PRO PADDLE_PRICE_ID_SELF_HOSTED_ENTERPRISE

render_template() {
  local template_path="$1"
  local output_path="$2"
  python3 - <<'PY' "$template_path" "$output_path"
from pathlib import Path
from string import Template
import os
import sys

src = Path(sys.argv[1])
dst = Path(sys.argv[2])
dst.write_text(Template(src.read_text()).substitute(os.environ), encoding='utf-8')
PY
}

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

render_template "$K8S_DIR/configmap.yaml.tmpl" "$TMP_DIR/configmap.yaml"
render_template "$K8S_DIR/license-server-configmap.yaml.tmpl" "$TMP_DIR/license-server-configmap.yaml"
render_template "$K8S_DIR/api-deployment.yaml.tmpl" "$TMP_DIR/api-deployment.yaml"
render_template "$K8S_DIR/worker-deployment.yaml.tmpl" "$TMP_DIR/worker-deployment.yaml"
render_template "$K8S_DIR/license-server-deployment.yaml.tmpl" "$TMP_DIR/license-server-deployment.yaml"
render_template "$K8S_DIR/api-service.yaml.tmpl" "$TMP_DIR/api-service.yaml"
render_template "$K8S_DIR/license-server-service.yaml.tmpl" "$TMP_DIR/license-server-service.yaml"
render_template "$K8S_DIR/api-ingress.yaml.tmpl" "$TMP_DIR/api-ingress.yaml"

kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/cloud/deploy.yaml
kubectl -n ingress-nginx rollout status deployment/ingress-nginx-controller --timeout=10m

TLS_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR" "$TLS_DIR"' EXIT
openssl req -x509 -nodes -newkey rsa:2048 \
  -keyout "$TLS_DIR/tls.key" \
  -out "$TLS_DIR/tls.crt" \
  -days 365 \
  -subj "/CN=${API_DOMAIN}" \
  -addext "subjectAltName=DNS:${API_DOMAIN},DNS:${LICENSE_DOMAIN}" >/dev/null 2>&1

kubectl -n vigilweave delete secret api-tls --ignore-not-found >/dev/null
kubectl -n vigilweave create secret tls api-tls \
  --cert="$TLS_DIR/tls.crt" \
  --key="$TLS_DIR/tls.key" >/dev/null

kubectl apply -f "$TMP_DIR/configmap.yaml"
kubectl apply -f "$TMP_DIR/license-server-configmap.yaml"
kubectl apply -f "$TMP_DIR/api-deployment.yaml"
kubectl apply -f "$TMP_DIR/worker-deployment.yaml"
kubectl apply -f "$TMP_DIR/license-server-deployment.yaml"
kubectl apply -f "$TMP_DIR/api-service.yaml"
kubectl apply -f "$TMP_DIR/license-server-service.yaml"
kubectl apply -f "$TMP_DIR/api-ingress.yaml"

kubectl -n vigilweave rollout restart deployment/api deployment/worker deployment/license-server

kubectl -n vigilweave rollout status deployment/api --timeout=10m
kubectl -n vigilweave rollout status deployment/worker --timeout=10m
kubectl -n vigilweave rollout status deployment/license-server --timeout=10m

INGRESS_PUBLIC_IP="$(kubectl -n ingress-nginx get svc ingress-nginx-controller -o jsonpath='{.status.loadBalancer.ingress[0].ip}')"

cat <<EOF

Deployment complete.

Cloudflare DNS to add:
- ${ROOT_DOMAIN} -> proxied CNAME ${STORAGE_WEB_HOST}
- ${APP_DOMAIN} -> proxied CNAME ${STORAGE_WEB_HOST}
- ${API_DOMAIN} -> proxied A ${INGRESS_PUBLIC_IP}
- ${LICENSE_DOMAIN} -> proxied A ${INGRESS_PUBLIC_IP}

Cloudflare SSL/TLS mode:
- Set the zone to Full

Useful checks:
- Static site endpoint: https://${STORAGE_WEB_HOST}
- API health once DNS resolves: https://${API_DOMAIN}/health
- License server health once DNS resolves: https://${LICENSE_DOMAIN}/health
- AKS ingress IP: ${INGRESS_PUBLIC_IP}

Generated env file: ${ENV_FILE}

EOF
