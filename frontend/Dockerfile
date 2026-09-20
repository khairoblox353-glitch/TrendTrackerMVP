# Trend Tracker frontend image.
#
# Multi-stage: dependencies and the production build happen in `builder`; the runtime
# stage carries only the standalone server output (see `output: "standalone"` in
# next.config.ts), which keeps the final image small.

FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci


FROM node:22-alpine AS builder
WORKDIR /app

ENV NEXT_TELEMETRY_DISABLED=1

COPY --from=deps /app/node_modules ./node_modules
COPY . .

# The build performs server-side data fetches against the API. This value only needs
# to be reachable during the build; the runtime value comes from the environment.
ARG API_BASE_URL=http://backend:8000
ENV API_BASE_URL=${API_BASE_URL}

RUN npm run build


FROM node:22-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

RUN addgroup --system --gid 1001 nodejs \
    && adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000

# Healthcheck must use 127.0.0.1, not `localhost`: busybox wget resolves `localhost` to
# IPv6 `::1` first, and the Next.js standalone server binds IPv4 only, so the check would
# report the container unhealthy while it serves traffic normally.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD wget --spider -q http://127.0.0.1:3000/ || exit 1

CMD ["node", "server.js"]
