# ── Stage 1: builder ─────────────────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

# Install deps first (better layer caching — only reinstalled when lockfile changes)
COPY package.json package-lock.json* ./
RUN npm ci

# Copy source and build
COPY . .
RUN npm run build


# ── Stage 2: production image ─────────────────────────────────────────────────
FROM nginx:alpine

# SPA routing: unknown paths fall back to /index.html so React Router handles them
RUN printf 'server {\n\
    listen 80;\n\
    root /usr/share/nginx/html;\n\
    index index.html;\n\
\n\
    # All routes fall through to index.html for client-side routing\n\
    location / {\n\
        try_files $uri $uri/ /index.html;\n\
    }\n\
\n\
    # Static assets — long cache TTL since they are content-addressed\n\
    location ~* \\.(?:js|css|woff2?|ico|png|jpg|jpeg|svg|gif|webp)$ {\n\
        expires 1y;\n\
        add_header Cache-Control "public, immutable";\n\
    }\n\
}\n' > /etc/nginx/conf.d/default.conf

COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
