ARCHIVED: replaced by docs/ARCHITECTURE.md, docs/FLOWS.md, docs/VERIFYING.md

Plan: Projekt → Fort Knox (utan n8n)
0) Princip: “KnoxInputPack” är den enda exportformen

Vi exporterar aldrig “projektet” som diffusa objekt. Vi bygger alltid ett KnoxInputPack som är:

deterministiskt (samma projekt + samma policy → samma fingerprint)

text-minimerat (endast masked/sanitized fält)

policy-låst (sanitize_min_level + citat/datumsregler)

1) Backend: bygg KnoxInputPack (deterministiskt)

Input: project_id, policy_id, template_id

Pack-innehåll (v1):

project: { id, name, tags, status, created_at }

documents[] (SORTERA alltid på created_at, sen id):

{ doc_id, sha256, sanitize_level, updated_at, masked_text }

notes[] (valfritt i v1, men jag tycker vi tar med direkt):

{ note_id, updated_at, sanitize_level, masked_body }

sources[] (ingen text-extraktion här):

{ source_id, type, title, url }

Manifest & fingerprint (utan innehåll):

input_manifest = [{type, id, sha256, sanitize_level, updated_at}]

input_fingerprint = sha256(json_dumps_sorted(input_manifest))

Viktigt: fingerprint ska baseras på manifest (inte text), så vi kan bevisa exakt underlag utan att lagra innehåll.

2) Input-gate (innan något lämnar VPS)

Fail-closed om något av detta sker:

sanitize_level < policy.sanitize_min_level

pii_gate_check fail på sammanfogad input (eller per block)

pack-size > max_bytes (t.ex. 300k–800k beroende på policy)

timeout eller fetch-problem

Resultat: ingen rapport skapas.

3) Skicka pack till FortKnox Local (Mac)

VPS anropar din Mac via privat nät (Tailscale rekommenderat):

POST http://<tailscale-ip>:8787/compile
Payload:

policy (id, version, mode, ruleset_hash)

template_id

input_fingerprint

documents[] masked_text blocks

notes[] masked_body blocks

Mac-tjänsten:

loggar aldrig text (bara metadata)

kör LLM (Ministral GGUF via llama.cpp server eller annan lokal engine)

returnerar strikt JSON enligt schema (ingen fri text)

4) Output-gate + re-id guard (på VPS)

När JSON kommer tillbaka:

rendera deterministiskt till Markdown (kod)

kör pii_gate_check på renderad markdown

kör re-id guard:

citatförbud (eller max 8 ord i följd från input)

external policy: inga exakta datum + inga “för specifika” kombinationer

Fail-closed: om något triggar → spara ingen rapport.

5) Spara KnoxReport (auditbar)

Spara:

report_id, project_id

policy_id, policy_version, ruleset_hash

engine_id (t.ex. ministral-3-8b-gguf-q4_k_m)

input_fingerprint

input_manifest (utan innehåll)

gate_results (pass/fail + reasons)

rendered_markdown (endast om pass)

timestamps, latency_ms

6) UI-flöde (på domänen)

I projektet: knapp “Skapa Fort Knox-rapport”

välj policy: Intern / Extern

välj mall: Weekly / Brief / Incident

klicka “Kompilera”

UI pollar status tills klar (eller visar fail reason – metadata-only)

7) Verifiering (obligatorisk “bevis att det funkar”)

verify-fortknox-v1 ska:

skapa projekt + docs + notes

compile internal → PASS

check: input_fingerprint finns, policy_version finns, JSON schema ok

compile external med fixture som “tvingar” citat/datum → ska FAILA deterministiskt

kör compile igen utan ändringar → ska ge:

antingen “skipped (same fingerprint)” eller ny report men samma fingerprint (du väljer, men det ska vara konsekvent)

Output: test_results/fortknox_v1_verify.json

En sak jag vill lägga till (för att slippa framtida strul)

Idempotensregel för KnoxReport
Välj en av två:

A) One-report-per-fingerprint-per-policy (min favorit):
om samma fingerprint + policy → returnera befintlig report (skippa compute).

B) Alltid ny report men med samma fingerprint:
enklare "historik", men mer compute.

Jag hade kört A för v1. Stabilt och billigt.

Prompt till Cursor (nästa steg, exakt)

Bygg Fort Knox “Project → KnoxInputPack → Local Compile → KnoxReport” enligt planen. Inför KnoxInputPack builder, input_manifest/fingerprint, input-gate, remote-call till fortknox-local, output-gate + re-id guard, deterministisk JSON→markdown render, spara KnoxReport, och verify-script + Make target. Rör inga andra filer än: apps/api/main.py, apps/api/fortknox.py (ny eller befintlig), apps/api/fortknox_remote.py (ny), apps/api/schemas.py, apps/api/_verify/verify_fortknox_v1.py, Makefile, ev tests/fixtures. Logga aldrig text, bara metadata. Fail-closed överallt.

PLAN – Fort Knox v1 med ProjectNote (utan n8n)

Mål
Frontend + API kör på din domän. Fort Knox-LLM kör lokalt på din Mac. Arbetsytan exporterar ett deterministiskt “KnoxInputPack” (endast sanitiserad text) till Fort Knox Local, får tillbaka strikt JSON, renderar deterministiskt, kör dubbel gate och sparar KnoxReport. Fail-closed hela vägen.

KnoxInputPack (deterministiskt exportformat)
Input: project_id, policy_id, template_id

Pack innehåller endast:
A) Projektmetadata (minimal)

project: { id, name, tags, status, created_at }

B) Documents (endast sanitiserad text)

documents[] sorteras deterministiskt (created_at asc, id asc)

varje doc: { doc_id, sha256, sanitize_level, updated_at, masked_text }

C) ProjectNotes (v1: med direkt)

notes[] sorteras deterministiskt (created_at asc, id asc)

varje note: { note_id, updated_at, sanitize_level, masked_body }

D) Sources (ingen text, bara metadata)

sources[] sorteras deterministiskt (type asc, id asc)

varje source: { source_id, type, title, url }

E) Policy + template metadata

policy: { policy_id, policy_version, ruleset_hash, mode, sanitize_min_level, quote_limit_words, date_strictness }

template_id

Manifest + fingerprint (utan innehåll)
Bygg input_manifest för bevisbar provenance utan text:

input_manifest = [
{ kind:"document", id:doc_id, sha256, sanitize_level, updated_at },
{ kind:"note", id:note_id, sha256_or_hash_of_masked_body, sanitize_level, updated_at },
{ kind:"source", id:source_id, url_hash, updated_at }
]

input_fingerprint = sha256(canonical_json(input_manifest))

Viktigt:

Inga masked_text/masked_body i manifest.

För notes: om du inte har en sha256 i modellen, beräkna sha256 på masked_body i runtime men lagra endast hashen i manifest.

Input-gate (innan något lämnar VPS)
Fail-closed om något av följande:

sanitize_level < policy.sanitize_min_level (gäller docs och notes)

pii_gate_check fail på sammanfogad “sanitized payload” (docs+notes i kontrollerad form)

pack_size > max_bytes (policy-styrt)

remote inte nåbar / timeout

Resultat vid fail: ingen KnoxReport skapas.

Remote-call till Fort Knox Local (Mac)
VPS backend anropar privat URL (Tailscale):

POST FORTKNOX_REMOTE_URL/compile

Payload:

policy metadata (utan hemligheter)

template_id

input_fingerprint

structured blocks:

documents: [{id, text: masked_text}]

notes: [{id, text: masked_body}]

sources: [{id, url, title, type}] (valfritt, men ingen fetch av url)

FortKnox Local:

loggar aldrig text

kör lokal LLM (Ministral 3 8B GGUF via llama.cpp server)

returnerar strikt JSON enligt schema (ingen fri text)

Output-gate + re-id guard (på VPS)
Efter remote-svar:

validera JSON schema (måste)

rendera deterministiskt till Markdown (kod)

kör pii_gate_check på renderad text

kör re-id guard:

citatförbud / max 8 ord i följd som matchar input

external policy: inga exakta datum, inga identifierande kombinationer (heuristik)
Fail-closed: vid fail → spara ingen rapport

KnoxReport (sparas i DB)
Spara:

report_id, project_id

policy_id, policy_version, ruleset_hash, template_id

engine_id (t.ex. ministral-3-8b-gguf-q4_k_m)

input_fingerprint

input_manifest (utan innehåll)

gate_results (pass/fail + reasons)

rendered_markdown (endast vid pass)

created_at, latency_ms

Idempotensregel (v1, rekommenderad)
One-report-per-fingerprint-per-policy:
Om samma (project_id + policy_id + template_id + input_fingerprint) redan finns → returnera den och “skippa compute”.

UI på domänen
I projektvyn:

Knapp “Skapa Fort Knox-rapport”

Dropdown: Intern / Extern

Dropdown: Mall (Weekly/Brief/Incident)

Kör → status → visa rapport → exportera/copy

Verifiering (obligatorisk)
Make target: verify-fortknox-v1

Verify-script ska:

skapa projekt + docs + notes

compile internal → PASS

assert: policy_version, ruleset_hash, input_fingerprint, manifest ok

compile external med fixture som provocerar citat/datum → FAIL deterministiskt

compile internal igen utan ändringar → dedupe (skipped/returned existing)
Output: test_results/fortknox_v1_verify.json

PROMPT TILL CURSOR (copy/paste)

Du arbetar i ARBETSYTAN-repot. Implementera Fort Knox v1 enligt planen nedan. Följ strikt: rör INGEN annan kod än de filer som explicit nämns. Refaktorera inte “lite runt omkring”. Inför ingen alternativ pipeline – återanvänd exakt befintlig säkerhetslogik (normalize → mask_text → pii_gate_check) och fail-closed vid minsta osäkerhet. Logga aldrig innehåll, bara metadata. Ingen mock om det inte uttryckligen krävs. Efter ändring: verifieringsscript måste PASSA.

Mål: Projekt → KnoxInputPack (documents + projectnotes) → privat remote-call till fortknox-local på min Mac → strikt JSON → deterministisk markdown render → output-gate → spara KnoxReport. Frontend+API kör på min domän, LLM kör lokalt.

Krav:

Bygg KnoxInputPack builder:

inkluderar Documents.masked_text och ProjectNote.masked_body (sanitiserade)

deterministisk sortering

input_manifest utan innehåll + input_fingerprint = sha256(canonical manifest json)

Input-gate på VPS:

sanitize_level >= policy.sanitize_min_level (docs + notes)

pii_gate_check på sammanfogad sanitized payload

max payload size + timeout
Fail-closed: skapa ingen rapport om fail.

Remote-call:

skapa apps/api/fortknox_remote.py som POST:ar till FORTKNOX_REMOTE_URL/compile (Tailscale URL)

timeout + max bytes + fail-closed

logga aldrig text

Output:

fortknox-local returnerar strikt JSON enligt schema

VPS validerar schema, renderar deterministiskt markdown (kod)

output-gate: pii_gate_check + re-id guard (citat/datumsregler för external)

KnoxReport persistens + idempotens:

one-report-per-fingerprint-per-policy+template

om fingerprint matchar befintlig report: returnera den, skippa compute

Verifiering:

apps/api/_verify/verify_fortknox_v1.py ska skapa projekt+docs+notes, köra internal PASS, external FAIL, rerun dedupe, och skriva test_results/fortknox_v1_verify.json

Makefile: verify-fortknox-v1

Filer som får röras/skapas (endast):

apps/api/main.py

apps/api/fortknox.py (ny eller befintlig)

apps/api/fortknox_remote.py (ny)

apps/api/schemas.py

apps/api/_verify/verify_fortknox_v1.py (ny)

Makefile

ev tests/fixtures (om behövs)

UI: ändra inte layout här.