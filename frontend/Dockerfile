# syntax=docker/dockerfile:1

# ExpenseFlow web app: build with the pinned Node + pnpm, serve the static build with
# nginx. nginx also proxies /api to the API container, so the browser makes
# same-origin calls exactly as it does through the Vite dev proxy (no CORS needed).

FROM node:26.13.1-alpine AS build

WORKDIR /app

# Node 25+ no longer ships corepack, so pnpm is installed at the version package.json pins.
RUN npm install --global pnpm@11.16.0

# Dependencies first so the layer is cached until the lock file changes.
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY . .
RUN pnpm build


FROM nginx:1.29-alpine AS runtime

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget --quiet --spider http://127.0.0.1/ || exit 1
