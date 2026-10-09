# The web app: a production build served by Vite's preview server.
# Built from the repository root.
FROM node:24-slim

RUN corepack enable

ENV NODE_ENV=production \
    HEALTH_API_URL=http://api:8000

WORKDIR /app

COPY web/package.json web/pnpm-lock.yaml web/pnpm-workspace.yaml web/.npmrc ./
RUN pnpm install --frozen-lockfile

COPY web ./
RUN pnpm build

EXPOSE 3000
CMD ["pnpm", "exec", "vite", "preview", "--host", "0.0.0.0", "--port", "3000", "--strictPort"]
