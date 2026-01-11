# Demo-script (10 minuter)

## Mål med demon
Visa en **verksamhetsnära loop** som stödjer redaktionellt arbete med **lokal AI** och **fail-closed** säkerhet.

## Förutsättningar
- Appen är igång via demo-deploy (Tailscale Funnel) eller lokalt via Caddy på `:8443`.
- Du har minst ett projekt med underlag (Scout-item eller uppladdat dokument).

## 1) Kontrollrum → Scout (1 min)
- Gå till **Kontrollrum**.
- Visa “Scout – senaste 7 dagar”.
- Klicka ett lead och **Skapa projekt**.

## 2) Projekt → Underlag (2 min)
- Visa att dokument/anteckning finns.
- Peka på att UI inte visar råa interna detaljer i listor (bara metadata).

## 3) Fort Knox Extern (4 min)
- Öppna **Fort Knox** i projektvyn och välj **Extern**.
- Peka på badges:
  - `strict`/`paranoid` krav
  - “Datum maskat” (icke-blockande info)
- Klicka **Kompilera Extern**.
  - Nämn: “**Lokal AI arbetar – kan ta upp till 3 min**” (så användaren inte tror att något hängt).
- Visa att output är redaktionellt användbar och att den går igenom output‑gates.

## 4) Spara rapport som dokument (1 min)
- Klicka **Spara som dokument**.
- Visa att rapporten dyker upp i dokumentlistan med ett bra filnamn (baserat på titel).

## 5) Deploy-story (2 min)
- Peka på att demon kör **på en domän**:
  - `/` frontend
  - `/api/*` backend
- Berätta kort: “TLS terminering via Tailscale Funnel, Caddy routar lokalt, inga publika portar”.

## 60 sek “varför detta är relevant”
- Integritet: lokal körning, ingen data lämnar datorn.
- Robusthet: fail-closed, idempotent rapportgenerering, metadata-only snapshots.
- Verksamhetsnära: bygger verktyg nära redaktionen och deras arbetsflöde.

