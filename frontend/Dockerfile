# =============================================================================
# Stage 1: Build Production Static Assets
# =============================================================================
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package manifests and install exact locked dependencies via npm ci
COPY package.json package-lock.json ./
RUN npm ci

# Copy application source and run TypeScript check + Vite production bundle
COPY . .
ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
RUN npm run build

# =============================================================================
# Stage 2: Production Nginx Static Runtime
# =============================================================================
FROM nginx:1.27-alpine AS runtime

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html

# Generate /usr/share/nginx/html/runtime-config.js at container startup from VITE_API_BASE_URL env var
RUN printf '#!/bin/sh\nset -e\ncat <<EOF > /usr/share/nginx/html/runtime-config.js\nwindow.__KH_RUNTIME_CONFIG__ = {\n  VITE_API_BASE_URL: "${VITE_API_BASE_URL:-}"\n};\nEOF\n' > /docker-entrypoint.d/40-generate-runtime-config.sh \
    && chmod +x /docker-entrypoint.d/40-generate-runtime-config.sh

EXPOSE 5173

HEALTHCHECK --interval=15s --timeout=5s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1:5173/ || exit 1

CMD ["nginx", "-g", "daemon off;"]

