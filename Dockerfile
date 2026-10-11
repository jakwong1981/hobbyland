FROM node:24-slim AS build
RUN corepack enable
WORKDIR /app

COPY pnpm-workspace.yaml package.json pnpm-lock.yaml tsconfig.base.json ./
COPY backend/package.json backend/
COPY frontend/package.json frontend/
RUN pnpm install --frozen-lockfile

COPY backend backend
COPY frontend frontend
RUN pnpm build

FROM node:24-slim AS runtime
RUN corepack enable
WORKDIR /app
ENV NODE_ENV=production \
    PORT=8080 \
    DATA_DIR=/data

COPY pnpm-workspace.yaml package.json pnpm-lock.yaml ./
COPY backend/package.json backend/
RUN pnpm --filter backend install --prod --frozen-lockfile

COPY --from=build /app/backend/dist backend/dist
COPY --from=build /app/backend/drizzle backend/drizzle
COPY --from=build /app/frontend/dist frontend/dist

EXPOSE 8080
VOLUME ["/data"]
CMD ["node", "backend/dist/index.js"]
