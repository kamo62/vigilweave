ARG BUILDPLATFORM
ARG TARGETPLATFORM

FROM python:3.14.3-slim AS runtime-base

ARG TARGETARCH
ARG GITLEAKS_VERSION=8.30.0
ARG TRIVY_VERSION=0.69.3
ARG TFLINT_VERSION=0.61.0
ARG DETEKT_VERSION=1.23.8
ARG DOTNET_VERSION=9.0.104
ARG SWIFTLINT_VERSION=0.63.2
ARG ANDROID_CMDLINE_TOOLS_VERSION=13114758
ARG ANDROID_PLATFORM=android-35
ARG ANDROID_BUILD_TOOLS=35.0.0

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TOOLCHAIN_PROFILE=base \
    PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential ca-certificates chromium curl git nodejs npm tar unzip \
    && npm install --global eslint@10.0.3 \
    && if [ "${TARGETARCH}" != "arm64" ]; then \
        echo "VigilWeave images are standardized on linux/arm64. Got TARGETARCH=${TARGETARCH}" && exit 1; \
      fi \
    && curl -fsSL \
      "https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/gitleaks_${GITLEAKS_VERSION}_linux_arm64.tar.gz" \
      | tar -xz -C /usr/local/bin gitleaks \
    && curl -fsSL \
      "https://github.com/aquasecurity/trivy/releases/download/v${TRIVY_VERSION}/trivy_${TRIVY_VERSION}_Linux-ARM64.tar.gz" \
      | tar -xz -C /usr/local/bin trivy \
    && curl -fsSL \
      "https://github.com/terraform-linters/tflint/releases/download/v${TFLINT_VERSION}/tflint_linux_arm64.zip" \
      -o /tmp/tflint.zip \
    && unzip -q /tmp/tflint.zip -d /tmp/tflint \
    && install -m 0755 /tmp/tflint/tflint /usr/local/bin/tflint \
    && rm -rf /tmp/tflint /tmp/tflint.zip \
    && curl -sSfL https://raw.githubusercontent.com/anchore/grype/main/install.sh | sh -s -- -b /usr/local/bin \
    && curl -sSfL https://raw.githubusercontent.com/anchore/syft/main/install.sh | sh -s -- -b /usr/local/bin \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY app app
COPY alembic alembic
COPY alembic.ini alembic.ini
COPY tools_config.yaml tools_config.yaml
COPY scripts scripts
COPY scripts/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

# Create non-root user for security (C8)
RUN groupadd -r vigilweave -g 1000 && \
    useradd -r -u 1000 -g vigilweave -d /app -s /bin/bash vigilweave && \
    mkdir -p /data && \
    chown -R vigilweave:vigilweave /app /data && \
    chmod +x /usr/local/bin/docker-entrypoint.sh

ENTRYPOINT ["docker-entrypoint.sh"]

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM runtime-base AS runtime-enterprise

USER root

ARG TARGETARCH
ARG DETEKT_VERSION
ARG DOTNET_VERSION
ARG SWIFTLINT_VERSION
ARG ANDROID_CMDLINE_TOOLS_VERSION
ARG ANDROID_PLATFORM
ARG ANDROID_BUILD_TOOLS

ENV TOOLCHAIN_PROFILE=enterprise \
    DOTNET_ROOT=/usr/share/dotnet \
    ANDROID_SDK_ROOT=/opt/android-sdk \
    ANDROID_HOME=/opt/android-sdk \
    PATH="/usr/share/dotnet:/opt/android-sdk/cmdline-tools/latest/bin:/opt/android-sdk/platform-tools:${PATH}"

RUN apt-get update \
    && apt-get install -y --no-install-recommends libxml2 openjdk-21-jdk-headless unzip \
    && if [ "${TARGETARCH}" != "arm64" ]; then \
        echo "VigilWeave enterprise image is standardized on linux/arm64. Got TARGETARCH=${TARGETARCH}" && exit 1; \
      fi \
    && curl -fsSL https://dot.net/v1/dotnet-install.sh -o /tmp/dotnet-install.sh \
    && bash /tmp/dotnet-install.sh --version "${DOTNET_VERSION}" --architecture arm64 --install-dir /usr/share/dotnet \
    && ln -sf /usr/share/dotnet/dotnet /usr/local/bin/dotnet \
    && mkdir -p /opt/detekt \
    && curl -fsSL \
      "https://github.com/detekt/detekt/releases/download/v${DETEKT_VERSION}/detekt-cli-${DETEKT_VERSION}-all.jar" \
      -o /opt/detekt/detekt-cli.jar \
    && printf '%s\n' '#!/usr/bin/env bash' 'exec java -jar /opt/detekt/detekt-cli.jar "$@"' > /usr/local/bin/detekt \
    && chmod +x /usr/local/bin/detekt \
    && curl -fsSL \
      "https://github.com/realm/SwiftLint/releases/download/${SWIFTLINT_VERSION}/swiftlint_linux_arm64.zip" \
      -o /tmp/swiftlint.zip \
    && unzip -q /tmp/swiftlint.zip -d /tmp/swiftlint \
    && install -m 0755 /tmp/swiftlint/swiftlint /usr/local/bin/swiftlint \
    && mkdir -p /opt/android-sdk/cmdline-tools /tmp/android \
    && curl -fsSL \
      "https://dl.google.com/android/repository/commandlinetools-linux-${ANDROID_CMDLINE_TOOLS_VERSION}_latest.zip" \
      -o /tmp/android/commandlinetools.zip \
    && unzip -q /tmp/android/commandlinetools.zip -d /tmp/android \
    && mv /tmp/android/cmdline-tools /opt/android-sdk/cmdline-tools/latest \
    && yes | sdkmanager --licenses >/dev/null \
    && sdkmanager \
      "platform-tools" \
      "platforms;${ANDROID_PLATFORM}" \
      "build-tools;${ANDROID_BUILD_TOOLS}" \
    && rm -rf /var/lib/apt/lists/* /tmp/android /tmp/dotnet-install.sh /tmp/swiftlint /tmp/swiftlint.zip
