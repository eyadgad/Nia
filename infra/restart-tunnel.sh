#!/usr/bin/env bash
# Re-expose the backend and point the deployed frontend at it.
#
# A trycloudflare quick tunnel is disposable by design. Its hostname is random, it cannot be
# reclaimed once the edge drops the registration, and cloudflared keeps the container running
# while it retries forever -- so "docker ps" says Up while the URL has been dead for hours,
# and the sign-in screen just says "API offline". Recovering means a new hostname, which the
# deployed frontend has to be rebuilt against, because NEXT_PUBLIC/rewrite destinations are
# baked at build time.
#
#   bash infra/restart-tunnel.sh
#
# For anything longer-lived than a testing round, a *named* tunnel on your own Cloudflare
# domain keeps one hostname across restarts and makes this script unnecessary.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NETWORK="${TUNNEL_NETWORK:-infra_default}"
ORIGIN="${TUNNEL_ORIGIN:-http://backend:8000}"

# A machine or Docker restart brings everything back at once, which is exactly when this
# script gets run -- and the backend is still starting while the tunnel is already up. Wait
# for it here rather than reading its silence as a broken tunnel.
echo "==> waiting for the backend to be ready"
for _ in $(seq 1 60); do
    state="$(docker inspect infra-backend-1 --format '{{.State.Health.Status}}' 2>/dev/null || echo missing)"
    [ "$state" = "healthy" ] && break
    sleep 2
done
if [ "${state:-}" != "healthy" ]; then
    echo "backend is ${state:-not running} after 120s; start the stack first" >&2
    exit 1
fi

echo "==> replacing the tunnel container"
docker rm -f nia-tunnel >/dev/null 2>&1 || true
# --protocol http2 because QUIC does not work from here. cloudflared's own precheck
# reports "UDP Connectivity ... QUIC connection failed" and suggests http2, then
# registers over QUIC anyway; the datagram handler dies minutes later, cloudflared
# exits, and the restart policy brings it back with a *different* random hostname --
# so the deployment ends up pointing at a URL that no longer exists. That chain is the
# whole reason this script kept being needed.
docker run -d --name nia-tunnel --restart unless-stopped --network "$NETWORK" \
    cloudflare/cloudflared:latest tunnel --no-autoupdate --protocol http2 \
    --url "$ORIGIN" >/dev/null

echo "==> waiting for a hostname"
URL=""
for _ in $(seq 1 40); do
    URL="$(docker logs nia-tunnel 2>&1 | grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' | head -1 || true)"
    [ -n "$URL" ] && break
    sleep 2
done
if [ -z "$URL" ]; then
    echo "no hostname after 80s; check: docker logs nia-tunnel" >&2
    exit 1
fi
echo "    $URL"

# A fresh quick-tunnel hostname is not in DNS the moment cloudflared prints it, and
# until it is, curl fails to connect rather than returning a status -- which reads
# identically to a broken backend. Wait for the name to exist before blaming anything
# behind it. If it never appears, say so plainly: Cloudflare hands these out at a
# limited rate, and after several in quick succession one can be issued and never
# published, in which case the only cure is to wait rather than make another.
HOST="${URL#https://}"
echo "==> waiting for $HOST to appear in DNS"
resolved=no
for _ in $(seq 1 40); do
    if getent hosts "$HOST" >/dev/null 2>&1; then resolved=yes; break; fi
    sleep 6
done
if [ "$resolved" != "yes" ]; then
    echo "$HOST never resolved (4 min). Cloudflare rate-limits quick tunnels; wait a" >&2
    echo "few minutes before retrying, or move to a named tunnel on your own domain." >&2
    exit 1
fi

echo "==> checking the backend answers through it"
for _ in $(seq 1 45); do
    code="$(curl -s -o /dev/null -m 20 -w '%{http_code}' "$URL/health" || true)"
    [ "$code" = "200" ] && break
    sleep 2
done
if [ "${code:-}" != "200" ]; then
    echo "tunnel is up but /health answered ${code:-nothing}; is the backend running?" >&2
    exit 1
fi

echo "==> pointing the deployment at it and rebuilding"
cd "$REPO_ROOT/frontend"
npx vercel env add BACKEND_ORIGIN production --value "$URL" --no-sensitive --force --yes >/dev/null
npx vercel --prod --yes >/dev/null

echo "==> verifying the deployed site"
for _ in $(seq 1 15); do
    code="$(curl -s -o /dev/null -m 25 -w '%{http_code}' https://nia-assistant.vercel.app/health || true)"
    [ "$code" = "200" ] && break
    sleep 3
done
if [ "${code:-}" != "200" ]; then
    echo "deployed /health answered ${code:-nothing}; the rebuild may still be propagating" >&2
    exit 1
fi

echo
echo "done. https://nia-assistant.vercel.app is serving again, backed by:"
echo "  $URL"
echo "to take it offline:  docker rm -f nia-tunnel"
