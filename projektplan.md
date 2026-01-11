## Projektplan (showreel polish)

Det här dokumentet är **styrande** för arbetet i repo:t. Vi bygger inte fler features förrän polish‑passet är klart.

### Principer (låsta)
- **Konsekvent UI**: samma komponent-familj överallt (knappar, inputs, cards, modals).
- **Stabilt & tryggt**: tydliga tomlägen/loading/error, inga “råa” stacktraces i UI.
- **Showreel‑säkert**: inga secrets i repo, inga raw content i loggar.
- **Minsta ändring som ger maximal effekt**.

### Phase 1 (status)
- [x] Projektstatus (redaktionellt läge)
- [x] Källor / referenser
- [x] Export / avslut
- [x] Röstmemo/transkription som dokument
- [x] Fort Knox “External” gate (datum maskas i pipeline, datum blockar inte)
- [x] Fort Knox: spara rapport som dokument (intern/extern)

### Showreel polish sprint (nu)
- [x] **Design-system light**: enhetliga `Button`, `Input`, `Select`, `Card`, `Modal` i alla nyckelvyer
- [x] **CI/supply-chain**: Dependabot + backend lint (ruff) för “industristandard”-känsla
- [x] **Observability light**: request-id + admin-skyddad `/api/metrics` (Prometheus)
- [x] **Rate limiting**: demo-safe throttling på upload + Fort Knox compile (429 vid missbruk)
- [x] **E2E smoke i CI**: health → skapa projekt → skapa note → `export_snapshot` (maskad vy)
- [x] **Spacing/typografi**: harmonisera rubriker, padding, list‑layout så det känns “premium”
- [x] **Tomlägen/loading/error**: polera i Scout, Projekt, Fort Knox (samma ton och layout)
- [x] **Copy-pass**: konsekvent svenska (ex: “Research/Bearbetning/Faktakoll/Klar/Arkiverad”)
- [x] **Responsivitet**: laptop-bredd + mindre (toolbar-wrap, modals, listor)
- [x] **Demo-check**: en snabb “happy path” genom hela appen utan visuella glitchar
- [x] **Demo: OpenAI API**: opt-in OpenAI för STT + Fort Knox LangChain via env (`STT_ENGINE=openai`, `FORTKNOX_LC_PROVIDER=openai`)
- [x] **Employer one-pager**: arkitektur + dataflöde + hotbild + fail-closed + “produktion vs demo” (`ONEPAGER.md`)

### Tekniska regler
- UI-komponenter ska bo i `apps/web/src/ui/`.
- Undvik duplicerad knapp‑CSS i pages/components – använd `.btn*` där det går.

