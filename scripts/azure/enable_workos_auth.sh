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
need_cmd python3

if [ ! -f "$ENV_FILE" ]; then
  printf 'Missing env file: %s\n' "$ENV_FILE" >&2
  exit 1
fi

set -a
. "$ENV_FILE"
set +a

LICENSE_SUBDOMAIN="${LICENSE_SUBDOMAIN:-license}"
PADDLE_ENVIRONMENT="${PADDLE_ENVIRONMENT:-sandbox}"
PADDLE_CLIENT_TOKEN="${PADDLE_CLIENT_TOKEN:-}"
PADDLE_API_KEY="${PADDLE_API_KEY:-}"
PADDLE_WEBHOOK_SECRET="${PADDLE_WEBHOOK_SECRET:-}"
PADDLE_PRICE_ID_PRO="${PADDLE_PRICE_ID_PRO:-}"
PADDLE_PRICE_ID_ENTERPRISE="${PADDLE_PRICE_ID_ENTERPRISE:-}"
PADDLE_PRICE_ID_SELF_HOSTED_PRO="${PADDLE_PRICE_ID_SELF_HOSTED_PRO:-}"
PADDLE_PRICE_ID_SELF_HOSTED_ENTERPRISE="${PADDLE_PRICE_ID_SELF_HOSTED_ENTERPRISE:-}"

: "${WORKOS_API_KEY:?Set WORKOS_API_KEY in $ENV_FILE}"
: "${WORKOS_CLIENT_ID:?Set WORKOS_CLIENT_ID in $ENV_FILE}"

RESOURCE_GROUP="${RESOURCE_GROUP:?}"
ACR_NAME="${ACR_NAME:?}"
POSTGRES_SERVER_NAME="${POSTGRES_SERVER_NAME:?}"
POSTGRES_ADMIN_USER="${POSTGRES_ADMIN_USER:?}"
POSTGRES_ADMIN_PASSWORD="${POSTGRES_ADMIN_PASSWORD:?}"
POSTGRES_DB_NAME="${POSTGRES_DB_NAME:?}"
REDIS_NAME="${REDIS_NAME:?}"
ROOT_DOMAIN="${ROOT_DOMAIN:?}"
API_SUBDOMAIN="${API_SUBDOMAIN:?}"
APP_SUBDOMAIN="${APP_SUBDOMAIN:?}"
LICENSE_SUBDOMAIN="${LICENSE_SUBDOMAIN:-license}"
IMAGE_TAG="${IMAGE_TAG:?}"

APP_DOMAIN="${APP_SUBDOMAIN}.${ROOT_DOMAIN}"
API_DOMAIN="${API_SUBDOMAIN}.${ROOT_DOMAIN}"
LICENSE_DOMAIN="${LICENSE_SUBDOMAIN}.${ROOT_DOMAIN}"
MARKETING_DOMAIN="${MARKETING_DOMAIN:-https://${ROOT_DOMAIN}}"
VIGILWEAVE_WEB_BASE_URL="https://${APP_DOMAIN}"
VIGILWEAVE_API_BASE_URL="https://${API_DOMAIN}"
WORKOS_REDIRECT_URI="${WORKOS_REDIRECT_URI:-https://${API_DOMAIN}/api/v1/auth/callback}"
WORKOS_COOKIE_DOMAIN="${WORKOS_COOKIE_DOMAIN:-.${ROOT_DOMAIN}}"
WORKOS_SESSION_SECRET="${WORKOS_SESSION_SECRET:-${SESSION_SECRET:-}}"
LICENSE_SERVER_API_BASE_URL="${LICENSE_SERVER_API_BASE_URL:-http://license-server}"
LICENSE_SERVER_URL="${LICENSE_SERVER_URL:-${LICENSE_SERVER_API_BASE_URL}/v1/verify}"
LICENSE_SERVER_ALLOWED_ORIGINS="${LICENSE_SERVER_ALLOWED_ORIGINS:-[\"https://${LICENSE_DOMAIN}\"]}"

if [ -z "$WORKOS_SESSION_SECRET" ]; then
  printf 'Set WORKOS_SESSION_SECRET or SESSION_SECRET in %s\n' "$ENV_FILE" >&2
  exit 1
fi

ACR_LOGIN_SERVER="$(az acr show --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" --query loginServer -o tsv)"
REDIS_HOST="$(az redis show --name "$REDIS_NAME" --resource-group "$RESOURCE_GROUP" --query hostName -o tsv)"
REDIS_KEY="$(az redis list-keys --name "$REDIS_NAME" --resource-group "$RESOURCE_GROUP" --query primaryKey -o tsv)"
POSTGRES_FQDN="$(az postgres flexible-server show --name "$POSTGRES_SERVER_NAME" --resource-group "$RESOURCE_GROUP" --query fullyQualifiedDomainName -o tsv)"

DATABASE_URL="postgresql+psycopg://${POSTGRES_ADMIN_USER}:${POSTGRES_ADMIN_PASSWORD}@${POSTGRES_FQDN}:5432/${POSTGRES_DB_NAME}?sslmode=require"
REDIS_URL="rediss://:${REDIS_KEY}@${REDIS_HOST}:6380/0?ssl_cert_reqs=required"
API_IMAGE="${ACR_LOGIN_SERVER}/vigilweave-api:${IMAGE_TAG}"

kubectl -n vigilweave create secret generic vigilweave-secrets \
  --dry-run=client -o yaml \
  --from-literal=SESSION_SECRET="$SESSION_SECRET" \
  --from-literal=TOKEN_ENCRYPTION_KEY="$TOKEN_ENCRYPTION_KEY" \
  --from-literal=WORKOS_API_KEY="$WORKOS_API_KEY" \
  --from-literal=WORKOS_CLIENT_ID="$WORKOS_CLIENT_ID" \
  --from-literal=WORKOS_REDIRECT_URI="$WORKOS_REDIRECT_URI" \
  --from-literal=WORKOS_COOKIE_DOMAIN="$WORKOS_COOKIE_DOMAIN" \
  --from-literal=WORKOS_SESSION_SECRET="$WORKOS_SESSION_SECRET" \
  --from-literal=PADDLE_API_KEY="${PADDLE_API_KEY:-}" \
  --from-literal=PADDLE_WEBHOOK_SECRET="${PADDLE_WEBHOOK_SECRET:-}" \
  --from-literal=LICENSE_SERVER_SHARED_SECRET="${LICENSE_SERVER_SHARED_SECRET:-}" \
  | kubectl apply -f -

export DATABASE_URL REDIS_URL TOOLCHAIN_PROFILE CELERY_CONCURRENCY VIGILWEAVE_WEB_BASE_URL
export VIGILWEAVE_API_BASE_URL WORKOS_COOKIE_DOMAIN API_IMAGE WORKER_REPLICAS API_DOMAIN
export MARKETING_DOMAIN SESSION_AUTH_PROVIDER=workos API_KEYS_ENABLED=true SAAS_ENABLED=true LICENSE_TESTING_MODE=false
export LICENSE_SERVER_URL LICENSE_SERVER_API_BASE_URL LICENSE_SERVER_ALLOWED_ORIGINS
export PADDLE_ENVIRONMENT PADDLE_CLIENT_TOKEN PADDLE_PRICE_ID_PRO PADDLE_PRICE_ID_ENTERPRISE
export PADDLE_PRICE_ID_SELF_HOSTED_PRO PADDLE_PRICE_ID_SELF_HOSTED_ENTERPRISE

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

python3 - <<'PY' "$K8S_DIR/configmap.yaml.tmpl" "$TMP_DIR/configmap.yaml" "$K8S_DIR/api-deployment.yaml.tmpl" "$TMP_DIR/api-deployment.yaml" "$K8S_DIR/worker-deployment.yaml.tmpl" "$TMP_DIR/worker-deployment.yaml"
from pathlib import Path
from string import Template
import os
import sys

args = sys.argv[1:]
for src, dst in zip(args[0::2], args[1::2]):
    Path(dst).write_text(Template(Path(src).read_text()).substitute(os.environ), encoding='utf-8')
PY

kubectl apply -f "$TMP_DIR/configmap.yaml"
kubectl apply -f "$TMP_DIR/api-deployment.yaml"
kubectl apply -f "$TMP_DIR/worker-deployment.yaml"
kubectl -n vigilweave rollout restart deployment/api deployment/worker
kubectl -n vigilweave rollout status deployment/api --timeout=20m
kubectl -n vigilweave rollout status deployment/worker --timeout=20m

printf 'WorkOS auth enabled for %s with callback %s\n' "$APP_DOMAIN" "$WORKOS_REDIRECT_URI"
