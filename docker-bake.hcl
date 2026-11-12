group "default" {
  targets = ["api", "worker", "frontend"]
}

group "enterprise" {
  targets = ["api-enterprise", "worker-enterprise"]
}

target "common" {
  context = "."
  platforms = ["linux/arm64"]
}

target "api" {
  inherits = ["common"]
  dockerfile = "Dockerfile"
  tags = ["vigilweave-api:latest"]
}

target "worker" {
  inherits = ["common"]
  dockerfile = "Dockerfile"
  tags = ["vigilweave-worker:latest"]
}

target "api-enterprise" {
  inherits = ["common"]
  dockerfile = "Dockerfile"
  target = "runtime-enterprise"
  tags = ["vigilweave-api-enterprise:latest"]
}

target "worker-enterprise" {
  inherits = ["common"]
  dockerfile = "Dockerfile"
  target = "runtime-enterprise"
  tags = ["vigilweave-worker-enterprise:latest"]
}

target "frontend" {
  inherits = ["common"]
  dockerfile = "frontend/Dockerfile"
  tags = ["vigilweave-frontend:latest"]
}
