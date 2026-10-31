# Running Vocab Sensei for friends

The app runs on this Mac in Docker, and a tunnel (free **Tailscale Funnel**, or Cloudflare) gives it a public
`https://` address without opening any ports on your router. Everything here is free and open source; it is online while the
Mac is awake.

```
friends' browsers ──https──▶ Tailscale Funnel (or Cloudflare) ──tunnel──▶ web (Caddy: app + /api) ─▶ api ─▶ db (PostgreSQL)
```

## 1. Install Docker (once)

[Colima](https://github.com/abiosoft/colima) (MIT) runs the open-source Docker engine in a small VM; no Docker Desktop needed.

```bash
brew install colima docker docker-compose
mkdir -p ~/.docker/cli-plugins && ln -sfn "$(brew --prefix)/opt/docker-compose/bin/docker-compose" ~/.docker/cli-plugins/docker-compose
colima start --cpu 2 --memory 4     # after a reboot, run this again (or `brew services start colima`)
docker run --rm hello-world         # checks it works
```

## 2. Configure

```bash
cd deploy
cp .env.example .env               # then edit .env
```

- `POSTGRES_PASSWORD`: any long random string (`openssl rand -base64 24`).
- Email: friends must verify their address, so fill in the Gmail settings (an app password, not your normal
  password).
- `VOCAB_EMAIL__APP_BASE_URL`: the public URL from step 4 (links in emails point there).

## 3. Start

```bash
docker compose up -d --build       # first start: a few minutes (images + WordNet download)
docker compose ps                  # api and web should say "healthy" / "running"
open http://localhost:8080         # the app, on this Mac only
```

## 4. Put it online

**Fixed address for free (what this Mac uses): Tailscale Funnel.** Install the Tailscale app
(`brew install --cask tailscale`), open it and log in, then publish the site:

```bash
tailscale funnel --bg 8080      # the first time it prints a link to enable Funnel; approve it, run again
tailscale funnel status         # shows the public address, e.g. https://<mac-name>.<tailnet>.ts.net
```

Tailscale keeps this after reboots, and its certificate gives the site HTTPS. Set `VOCAB_EMAIL__APP_BASE_URL` in `.env` to that
address and run `docker compose up -d --force-recreate api` so email links use it. To stop publishing:
`tailscale funnel --https=443 off`.

**Quick try (no account):** a random `https://….trycloudflare.com` address that changes on every restart.

```bash
docker compose --profile quick-tunnel up -d
docker compose logs quick-tunnel | grep trycloudflare.com
```

**Your own domain:** a free Cloudflare account and a domain on Cloudflare. In Cloudflare
**Zero Trust → Networks → Tunnels → Create a tunnel** (type *Cloudflared*), choose *Docker*, copy the token into
`TUNNEL_TOKEN` in `.env`, add a **public hostname** (e.g. `vocab.yourdomain.com`) pointing to `http://web:80`, then
`docker compose --profile tunnel up -d`.

## Everyday commands

```bash
docker compose logs -f api                      # what the backend is doing
git pull && docker compose up -d --build        # update to the latest version (migrations run on start)
docker compose down                             # stop (data stays in the pgdata/appdata volumes)
docker compose exec db pg_dump -U vocab vocab_sensei > backup.sql   # a backup right now
```

## Backups

The `backup` service writes a compressed database dump every day to `deploy/backups/`
(`vocab_sensei-YYYY-MM-DD.sql.gz`, the last 7 days are kept; check with `ls deploy/backups`). Uploaded book
files aren't included; they can be uploaded again, and the classics are re-downloaded automatically.

To restore one (this **replaces** the current data):

```bash
docker compose stop api
docker compose exec -T db psql -U vocab -d postgres -c "DROP DATABASE vocab_sensei;" -c "CREATE DATABASE vocab_sensei OWNER vocab;"
gunzip -c backups/vocab_sensei-2026-11-01.sql.gz | docker compose exec -T db psql -U vocab -d vocab_sensei
docker compose start api
```

Each user can also download their own progress from **Profile → Progress → Download a backup**.
