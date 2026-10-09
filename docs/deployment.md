# Deployment

The production stack runs on health-box, a home server. It is reachable from
the home network only. Machine settings and access are in the homelab
repository (`hosts/health-box.md`); this file covers the application.

## What runs

`compose.prod.yaml` starts four services in one Compose project:

| Service | Runs | Reachable at |
| --- | --- | --- |
| `postgres` | PostgreSQL 18, data in the `postgres-data` volume | nowhere outside the project; no published port |
| `migrate` | `python -m health_api.migrate`, then exits | nowhere |
| `api` | the health API | `127.0.0.1:8000` on the server (Hermes and local tools) |
| `web` | the web app | `http://health.fritz.box` (home network, port 80) |

`migrate` finishes before `api` starts, so every start brings the database up to
date. Nothing is published on `0.0.0.0`, and the database never is.

The web app has no login. That was accepted on 2026-10-09 for the home network,
see the homelab repository.

## Files on the server

- `~/health/`: a copy of this repository, written by the deploy script.
- `~/health/.env`: `HEALTH_DB_PASSWORD`. Created once by hand, never copied from
  a deploy and never committed. Start from `.env.prod.example`, and generate the
  password with `openssl rand -hex 24`, since it goes into a connection URL.
- `~/health-backups/`: nightly dumps. Kept on the server only.

## Deploy

From the MacBook:

```sh
scripts/deploy-health-box.sh
```

The script copies the repository with rsync (excluding `.env`, backups, photos
and build output), runs `docker compose -f compose.prod.yaml up --detach --build --wait`
on the server, and installs the backup timer. A deploy does not touch the
database volume, `.env` or the dumps.

Schema changes go in `db/migrations/` (see [Database](database.md)) and reach
the server through `migrate` on the next deploy.

## First-time setup

1. Install Docker on the server from Docker's apt repository, and add the user
   to the `docker` group. Membership in that group is root-equivalent, which is
   accepted for this single-user machine.
2. Create `~/health/.env` with a generated `HEALTH_DB_PASSWORD`.
3. Run the deploy script. This starts an empty database, with the baseline and
   migrations applied.
4. Move the data: on the MacBook, `make db-backup`. Then stop the app containers,
   copy the dump to the server, restore it, and start them again:

   ```sh
   scp backups/<dump> fabian@192.168.178.161:health-backups/import.dump
   ssh fabian@192.168.178.161 'cd health && docker compose -f compose.prod.yaml stop api web &&
     docker compose -f compose.prod.yaml exec -T postgres pg_restore -U health -d health \
       --clean --if-exists --no-owner < ~/health-backups/import.dump &&
     docker compose -f compose.prod.yaml up --detach --wait'
   ```

   Then check that counts match the MacBook database. From then on, the server is
   the source of truth. The MacBook keeps its development database, which is not
   synchronised with the server.

5. Check the publishing rules from the MacBook: the web app answers on
   `http://health.fritz.box`, `192.168.178.161:8000` is refused, and port 5432 is
   refused.

## Backups

`health-backup.timer` runs `scripts/backup-db.sh` every night at 03:20:

- writes a custom-format dump to `~/health-backups/`;
- checks the dump with `pg_restore --list` before keeping it;
- deletes dumps older than 14 days (`HEALTH_BACKUP_KEEP_DAYS`).

Nothing is copied off the server. Run a backup by hand with
`~/health/scripts/backup-db.sh`, or check the timer with
`systemctl list-timers health-backup.timer`.

To restore a dump, use the same command as in step 4 with the dump's path.

## Known limits

- The web app runs under Vite's preview server. That is Vite's own production
  preview, not a hardened web server. It is acceptable for one user on the home
  network, and it should be replaced before the app is reachable from anywhere
  else.
- No login on the web app (accepted 2026-10-09).
- Everything is on one disk. The nightly dumps protect against mistakes and
  corruption, not against losing the server. Copies off the machine are
  deliberately not made.
