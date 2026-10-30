# Majordomo web app: built with Vite, served by Caddy.
# Both node:22-alpine and caddy:2-alpine are multi-arch (amd64 + arm64).
# The build stage runs on the build machine's own platform for speed,
# because its output (static files) is the same for every architecture.
FROM --platform=$BUILDPLATFORM node:22-alpine AS build
WORKDIR /web
COPY package.json package-lock.json ./
RUN npm ci --no-fund --no-audit
COPY . .
RUN npm run build

FROM caddy:2-alpine
COPY Caddyfile /etc/caddy/Caddyfile
COPY --from=build /web/dist /srv
EXPOSE 80 443
