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

echo "==> replacing the tunnel container"
docker rm -f nia-tunnel >/dev/null 2>&1 || true
docker run -d --name nia-tunnel --restart unless-stopped --network "$NETWORK" \
    cloudflare/cloudflared:latest tunnel --no-autoupdate --url "$ORIGIN" >/dev/null

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

echo "==> checking the backend answers through it"
for _ in $(seq 1 15); do
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
