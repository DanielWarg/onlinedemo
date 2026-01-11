# PRINCIPLES.md

Non-negotiable principer för Arbetsytan.

- **Security by default** – Säkerhet kräver inga användarval; det är standard
- **Maskad vy är standard** – Alla arbetar i maskerad miljö som utgångspunkt; originalmaterial exponeras aldrig
- **Fail-closed vid osäkerhet** – Vid osäkerhet stängs systemet ner; ingen "fail-open"
- **Enkelhet över alternativ** – Färre val är bättre än många alternativ
- **Lokal STT** – Tal-till-text körs lokalt via openai-whisper; ingen data lämnar systemet
- **External AI endast via masked export, opt-in** – Externa AI-tjänster (ej implementerat) skulle endast användas med maskerat material och kräva explicit godkännande
- **Källskyddstänk** – Ingen övervakning av användare; loggar endast för incidenter och säkerhet
- **Demo-first scope guard** – Prioritera fungerande demo över komplett lösning
- **Production mindset** – Systemet ska vara observerbart, reversibelt och kostnadsmedvetet

