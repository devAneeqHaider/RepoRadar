# ---- Build stage ------------------------------------------------------------
FROM node:20-alpine AS build

WORKDIR /app

# Install dependencies first for better layer caching
COPY package.json package-lock.json* ./
RUN npm ci

# Build the production bundle
COPY . .
# Allow the API base URL to be injected at build time:
#   docker build --build-arg VITE_API_URL=https://api.example.com .
ARG VITE_API_URL
ENV VITE_API_URL=${VITE_API_URL}
RUN npm run build

# ---- Serve stage ------------------------------------------------------------
FROM nginx:alpine

# Single-page app: fall back to index.html for client-side routes
COPY --from=build /app/dist /usr/share/nginx/html
RUN printf 'server {\n\
  listen 80;\n\
  server_name _;\n\
  root /usr/share/nginx/html;\n\
  index index.html;\n\
  location / {\n\
    try_files $uri $uri/ /index.html;\n\
  }\n\
}\n' > /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
