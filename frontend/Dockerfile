FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json ./
COPY package-lock.json ./
RUN npm ci

FROM node:22-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
# NEXT_PUBLIC_* is read at build time, not at run time, so these have to arrive here rather
# than in the service environment. Empty is fine and is the default: the sign-in screen then
# simply does not render the credentials block.
ARG NEXT_PUBLIC_TEST_USERNAME=""
ARG NEXT_PUBLIC_TEST_PASSWORD=""
ENV NEXT_PUBLIC_TEST_USERNAME=$NEXT_PUBLIC_TEST_USERNAME
ENV NEXT_PUBLIC_TEST_PASSWORD=$NEXT_PUBLIC_TEST_PASSWORD
RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV HOSTNAME=0.0.0.0
ENV PORT=3000
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
