# Web: Express API + built React app. Build from the repo root:
#   docker build -f web/Dockerfile .
FROM node:24-slim AS build
WORKDIR /app/web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM node:24-slim
ENV NODE_ENV=production NA_WEB_HOST=0.0.0.0 NA_WEB_PORT=8000
WORKDIR /app/web
COPY web/package.json web/package-lock.json ./
RUN npm ci --omit=dev
COPY web/server ./server
COPY --from=build /app/web/dist ./dist
# config/ and data/ are mounted at /app/config and /app/data by docker-compose.
EXPOSE 8000
CMD ["node", "server/index.ts"]
