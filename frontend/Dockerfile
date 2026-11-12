FROM oven/bun:1.3.10 AS build

ARG VITE_API_BASE_URL=http://localhost:8000
ARG VITE_MARKETING_URL=
ARG VITE_APP_URL=
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
ENV VITE_MARKETING_URL=${VITE_MARKETING_URL}
ENV VITE_APP_URL=${VITE_APP_URL}

WORKDIR /app

COPY frontend/package.json frontend/bun.lock ./
RUN bun install --frozen-lockfile

COPY frontend .
COPY docs/openapi.json ../docs/openapi.json

RUN bun run build

FROM nginx:1.29-alpine

COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
