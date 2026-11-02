#!/bin/sh
# Keeps the friends' site reachable: starts Docker (Colima) and the stack, Tailscale and Funnel
# again if any of them is down. launchd runs it every 30 minutes (see deploy/README.md).
set -u
PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin
cd "$(dirname "$0")/.." || exit 1 # deploy/, where compose.yaml and .env live
TAILSCALE=/Applications/Tailscale.app/Contents/MacOS/Tailscale

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*"; }

# 1. Docker and the app
if ! colima status >/dev/null 2>&1; then
	log "Docker (Colima) is down: starting it"
	colima start >/dev/null 2>&1 || log "colima start failed"
fi
if ! curl -fsS -m 10 http://localhost:8080/api/health >/dev/null 2>&1; then
	log "the site isn't answering on this Mac: starting the stack"
	docker compose up -d >/dev/null 2>&1 || log "docker compose up failed"
fi

# 2. Tailscale (the app must be open for the CLI to work)
if ! "$TAILSCALE" status --json 2>/dev/null | grep -q '"BackendState": "Running"'; then
	log "Tailscale isn't running: opening the app and connecting"
	open -a Tailscale
	sleep 15
	"$TAILSCALE" up >/dev/null 2>&1 || log "tailscale up failed"
fi

# 3. Funnel: the public address
if ! "$TAILSCALE" funnel status 2>/dev/null | grep -q "Funnel on"; then
	log "Funnel is off: publishing the site again"
	"$TAILSCALE" funnel --bg 8080 >/dev/null 2>&1 || log "tailscale funnel failed"
fi
