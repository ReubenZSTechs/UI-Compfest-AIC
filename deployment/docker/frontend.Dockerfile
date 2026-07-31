# ---------- Stage 1: Build ----------
FROM node:20-alpine AS builder
WORKDIR /app

# Copy manifest dulu biar layer cache npm install efisien
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

# Copy source lalu build
COPY frontend/ ./

# Build-time env vars (contoh: VITE_API_URL), override lewat --build-arg
ARG VITE_API_URL=/api
ENV VITE_API_URL=${VITE_API_URL}
RUN npm run build

# ---------- Stage 2: Serve ----------
FROM nginx:1.27-alpine AS runner

# Hapus default nginx config, ganti dengan config custom (SPA fallback + proxy /api)
RUN rm /etc/nginx/conf.d/default.conf
COPY deployment/nginx/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget -qO- http://localhost:80/ || exit 1
CMD ["nginx", "-g", "daemon off;"]