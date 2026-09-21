# Arkitektur

## Oversikt

Frontend kommuniserer med backend via et versjonert API. Backend eier domene- og datatilgang. Infrastruktur holdes i `infra/`.

## Prinsipper

- Tydelige ansvarsgrenser mellom klient, API og data.
- Konfigurasjon via miljøvariabler; aldri hemmeligheter i Git.
- API-kontrakter dokumenteres før klientintegrasjon.
- Observability og sikkerhet vurderes fra første deploybare versjon.

## Åpne valg

- Frontend-rammeverk
- Backend-språk/rammeverk
- Database og autentiseringsløsning
- Hosting og CI/CD
