# VigilWeave — Kubernetes Deployment Guide

> **Recommendation:** For most teams, [Docker Compose](../docker-compose.yml) is the simplest and recommended deployment method. Use Kubernetes when you need horizontal scaling, high availability, or integration with existing cluster infrastructure.

---

## Prerequisites

- Kubernetes 1.27+ cluster (EKS, AKS, GKE, or self-managed)
- `kubectl` configured with cluster access
- Container registry accessible from the cluster (ECR, ACR, GCR, Docker Hub, etc.)
- PostgreSQL 14+ (managed service recommended — RDS, Azure Database, Cloud SQL)
- Redis 7+ (managed service recommended — ElastiCache, Azure Cache, Memorystore)

## Architecture

VigilWeave deploys as four components:

```
┌─────────────────────────────────────────────────┐
│                   Ingress                        │
│         / → frontend    /api/ → api              │
└─────────┬──────────────────────┬────────────────┘
          │                      │
    ┌─────▼─────┐          ┌─────▼─────┐
    │ Frontend   │          │ API       │
    │ (nginx)    │          │ (uvicorn) │
    │ 2 replicas │          │ 2 replicas│
    └───────────┘          └─────┬─────┘
                                 │
                           ┌─────▼─────┐
                           │ Worker    │
                           │ (celery)  │
                           │ 2 replicas│
                           └─────┬─────┘
                                 │
                    ┌────────────┼────────────┐
                    │            │            │
              ┌─────▼───┐ ┌─────▼───┐ ┌──────▼──────┐
              │ Redis   │ │PostgreSQL│ │ PVC (data)  │
              │ (queue) │ │ (state)  │ │ (optional)  │
              └─────────┘ └─────────┘ └─────────────┘
```

---

## 1. Build and Push Images

Build the three container images and push to your registry:

```bash
# Set your registry prefix
export REGISTRY=your-registry.example.com/vigilweave

# API + Worker (same image, different command)
docker build --target runtime-base -t $REGISTRY/api:latest .
docker push $REGISTRY/api:latest

# Frontend
docker build -t $REGISTRY/frontend:latest \
  --build-arg VITE_API_BASE_URL=https://vigilweave.your-domain.com \
  -f frontend/Dockerfile .
docker push $REGISTRY/frontend:latest

# Enterprise toolchain (optional — adds .NET, Android, Swift, Kotlin analyzers)
docker build --target runtime-enterprise -t $REGISTRY/api:latest-enterprise .
docker push $REGISTRY/api:latest-enterprise
```

> **Note:** The API image is ARM64-only by default. If your cluster runs AMD64 nodes, you will need to modify the Dockerfile to remove the `TARGETARCH` check and adjust binary download URLs.

---

## 2. Namespace

```yaml
# namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: vigilweave
  labels:
    app.kubernetes.io/part-of: vigilweave
```

```bash
kubectl apply -f namespace.yaml
```

---

## 3. Secrets

```yaml
# secrets.yaml
apiVersion: v1
kind: Secret
metadata:
  name: vigilweave-secrets
  namespace: vigilweave
type: Opaque
stringData:
  # Required — generate with: openssl rand -hex 32
  SESSION_SECRET: "CHANGE-ME-generate-a-random-hex-string"

  # Required — PostgreSQL connection string
  DATABASE_URL: "postgresql://vigilweave:password@postgres-host:5432/vigilweave"

  # Optional — commercial license key (omit for Community tier)
  # LICENSE_KEY: "vw-pro-xxxx-xxxx-xxxx"

  # Optional — WorkOS credentials (for SaaS/Enterprise SSO)
  # WORKOS_API_KEY: "sk_live_..."
  # WORKOS_CLIENT_ID: "client_..."
```

```bash
kubectl apply -f secrets.yaml
```

---

## 4. ConfigMap

```yaml
# configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: vigilweave-config
  namespace: vigilweave
data:
  REDIS_URL: "redis://redis.vigilweave.svc.cluster.local:6379/0"
  SESSION_AUTH_PROVIDER: "local"
  API_KEYS_ENABLED: "true"
  CELERY_TASK_ALWAYS_EAGER: "false"
  TOOLCHAIN_PROFILE: "base"
  CELERY_CONCURRENCY: "4"
```

```bash
kubectl apply -f configmap.yaml
```

---

## 5. Redis

If you prefer a managed Redis service, skip this and update `REDIS_URL` in the ConfigMap.

```yaml
# redis.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
  namespace: vigilweave
  labels:
    app.kubernetes.io/name: redis
    app.kubernetes.io/part-of: vigilweave
spec:
  replicas: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: redis
  template:
    metadata:
      labels:
        app.kubernetes.io/name: redis
    spec:
      containers:
        - name: redis
          image: redis:7-alpine
          ports:
            - containerPort: 6379
          resources:
            requests:
              cpu: 100m
              memory: 128Mi
            limits:
              cpu: 250m
              memory: 256Mi
---
apiVersion: v1
kind: Service
metadata:
  name: redis
  namespace: vigilweave
spec:
  selector:
    app.kubernetes.io/name: redis
  ports:
    - port: 6379
      targetPort: 6379
```

```bash
kubectl apply -f redis.yaml
```

---

## 6. API Deployment

```yaml
# api.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
  namespace: vigilweave
  labels:
    app.kubernetes.io/name: api
    app.kubernetes.io/part-of: vigilweave
spec:
  replicas: 2
  selector:
    matchLabels:
      app.kubernetes.io/name: api
  template:
    metadata:
      labels:
        app.kubernetes.io/name: api
    spec:
      containers:
        - name: api
          image: your-registry.example.com/vigilweave/api:latest
          ports:
            - containerPort: 8000
          envFrom:
            - configMapRef:
                name: vigilweave-config
            - secretRef:
                name: vigilweave-secrets
          readinessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 10
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 15
            periodSeconds: 20
          resources:
            requests:
              cpu: 250m
              memory: 512Mi
            limits:
              cpu: "1"
              memory: 1Gi
---
apiVersion: v1
kind: Service
metadata:
  name: api
  namespace: vigilweave
spec:
  selector:
    app.kubernetes.io/name: api
  ports:
    - port: 8000
      targetPort: 8000
```

> **SQLite note:** If using SQLite instead of PostgreSQL (dev only), set `replicas: 1` and mount a PVC at `/data`. See the PVC section below. Multiple API replicas with SQLite will cause data corruption.

```bash
kubectl apply -f api.yaml
```

---

## 7. Worker Deployment

Workers run the same image as the API but with a Celery command. They do not need a Service since they pull work from Redis.

```yaml
# worker.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: worker
  namespace: vigilweave
  labels:
    app.kubernetes.io/name: worker
    app.kubernetes.io/part-of: vigilweave
spec:
  replicas: 2
  selector:
    matchLabels:
      app.kubernetes.io/name: worker
  template:
    metadata:
      labels:
        app.kubernetes.io/name: worker
    spec:
      containers:
        - name: worker
          image: your-registry.example.com/vigilweave/api:latest
          command:
            - celery
            - -A
            - app.core.celery_app.celery_app
            - worker
            - --loglevel=info
          envFrom:
            - configMapRef:
                name: vigilweave-config
            - secretRef:
                name: vigilweave-secrets
          resources:
            requests:
              cpu: 500m
              memory: 1Gi
            limits:
              cpu: "2"
              memory: 2Gi
```

Workers are CPU/memory intensive during scans. Adjust resource limits based on your scan workload. Each concurrent scan clones a repository and runs multiple security tools.

```bash
kubectl apply -f worker.yaml
```

---

## 8. Frontend Deployment

```yaml
# frontend.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: frontend
  namespace: vigilweave
  labels:
    app.kubernetes.io/name: frontend
    app.kubernetes.io/part-of: vigilweave
spec:
  replicas: 2
  selector:
    matchLabels:
      app.kubernetes.io/name: frontend
  template:
    metadata:
      labels:
        app.kubernetes.io/name: frontend
    spec:
      containers:
        - name: frontend
          image: your-registry.example.com/vigilweave/frontend:latest
          ports:
            - containerPort: 80
          readinessProbe:
            httpGet:
              path: /
              port: 80
            initialDelaySeconds: 3
            periodSeconds: 10
          resources:
            requests:
              cpu: 50m
              memory: 64Mi
            limits:
              cpu: 200m
              memory: 128Mi
---
apiVersion: v1
kind: Service
metadata:
  name: frontend
  namespace: vigilweave
spec:
  selector:
    app.kubernetes.io/name: frontend
  ports:
    - port: 80
      targetPort: 80
```

> **Important:** `VITE_API_BASE_URL` is baked into the frontend at build time (step 1). It must point to the public URL where the API is accessible (e.g., `https://vigilweave.your-domain.com`).

```bash
kubectl apply -f frontend.yaml
```

---

## 9. Ingress

This example uses the nginx ingress controller. Adjust annotations for your ingress controller (ALB, Traefik, etc.).

```yaml
# ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: vigilweave
  namespace: vigilweave
  annotations:
    nginx.ingress.kubernetes.io/proxy-body-size: "50m"
    # Uncomment for cert-manager TLS:
    # cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  ingressClassName: nginx
  # Uncomment for TLS:
  # tls:
  #   - hosts:
  #       - vigilweave.your-domain.com
  #     secretName: vigilweave-tls
  rules:
    - host: vigilweave.your-domain.com
      http:
        paths:
          - path: /api/
            pathType: Prefix
            backend:
              service:
                name: api
                port:
                  number: 8000
          - path: /health
            pathType: Exact
            backend:
              service:
                name: api
                port:
                  number: 8000
          - path: /
            pathType: Prefix
            backend:
              service:
                name: frontend
                port:
                  number: 80
```

```bash
kubectl apply -f ingress.yaml
```

---

## 10. PersistentVolumeClaim (SQLite dev mode only)

Only needed if you are using SQLite instead of PostgreSQL. Not recommended for production.

```yaml
# pvc.yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: vigilweave-data
  namespace: vigilweave
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
```

Mount in the API deployment by adding to the container spec:

```yaml
volumeMounts:
  - name: data
    mountPath: /data
volumes:
  - name: data
    persistentVolumeClaim:
      claimName: vigilweave-data
```

---

## 11. Scaling

### Horizontal Pod Autoscaler

```yaml
# hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api-hpa
  namespace: vigilweave
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api
  minReplicas: 2
  maxReplicas: 8
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: worker-hpa
  namespace: vigilweave
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: worker
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 60
```

### Scaling guidelines

| Component | Min Replicas | Scale Factor |
|-----------|-------------|--------------|
| API | 2 | Scale with request volume |
| Worker | 2 | Scale with scan queue depth; each worker handles `CELERY_CONCURRENCY` concurrent scans |
| Frontend | 2 | Minimal load — static files served by nginx |
| Redis | 1 | Single instance sufficient for most workloads; use managed Redis for HA |

---

## 12. Enterprise Configuration

For Enterprise deployments with the extended toolchain and WorkOS SSO:

1. Use the enterprise image: `your-registry/vigilweave/api:latest-enterprise`
2. Update the ConfigMap:

```yaml
data:
  TOOLCHAIN_PROFILE: "enterprise"
  SESSION_AUTH_PROVIDER: "workos"
  SAAS_ENABLED: "true"
```

3. Add WorkOS credentials to the Secret:

```yaml
stringData:
  WORKOS_API_KEY: "sk_live_..."
  WORKOS_CLIENT_ID: "client_..."
  WORKOS_REDIRECT_URI: "https://vigilweave.your-domain.com/api/v1/auth/callback"
```

---

## Quick Deploy (all manifests)

Apply all manifests at once:

```bash
kubectl apply -f namespace.yaml
kubectl apply -f secrets.yaml
kubectl apply -f configmap.yaml
kubectl apply -f redis.yaml
kubectl apply -f api.yaml
kubectl apply -f worker.yaml
kubectl apply -f frontend.yaml
kubectl apply -f ingress.yaml

# Verify
kubectl get pods -n vigilweave
kubectl get svc -n vigilweave
kubectl get ingress -n vigilweave
```

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| API pods crash on start | Missing `SESSION_SECRET` or `DATABASE_URL` | Check Secret values |
| Worker pods stuck in CrashLoopBackOff | Redis unreachable | Verify `REDIS_URL` in ConfigMap, check Redis pod |
| Frontend shows blank page | `VITE_API_BASE_URL` wrong at build time | Rebuild frontend image with correct URL |
| 502 from Ingress | API pods not ready | Check readiness probe, API logs |
| Scans fail to clone | Worker can't reach external git hosts | Check network policies, egress rules |
| Database locked errors | Multiple replicas with SQLite | Switch to PostgreSQL or set `replicas: 1` |
