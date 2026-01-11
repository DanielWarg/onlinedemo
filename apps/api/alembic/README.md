# Alembic (migrations) – showreel‑setup

Det här är ett **första steg** mot versionerade DB‑migreringar. Demo kör fortfarande `create_all()` + `init_db.sql` som bootstrap, men du kan slå på migrations när du vill.

## Lokalt (från `apps/api/`)

```bash
export DATABASE_URL="postgresql://arbetsytan:arbetsytan@localhost:5432/arbetsytan"
alembic -c alembic.ini upgrade head
```

## I docker (demo/prod‑compose)

- Sätt `ALEMBIC_UPGRADE=1` i `deploy/tailscale/.env` (valfritt).

## Varför
- För att det ska kännas som en senior kodbas: reproducibla deploys, spårbarhet och rollback‑tänk.

