FROM node:20-alpine AS builder

WORKDIR /app
# Use ARG only (not ENV) so build-time values are not baked into the image metadata
ARG VITE_API_URL
ARG VITE_TURNSTILE_SITE_KEY
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
RUN VITE_API_URL=${VITE_API_URL} VITE_TURNSTILE_SITE_KEY=${VITE_TURNSTILE_SITE_KEY} npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
