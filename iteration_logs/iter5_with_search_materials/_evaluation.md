# Iteration 5 — search_materials Tool aktiviert

## Vergleich Iter 4 → Iter 5 (alles brutto, EUR)

| Szenario | Iter 4 | **Iter 5** | Realistisch | Verdikt |
|----------|-------:|-----------:|------------:|---------|
| S1 Schlafzimmer | 891 | **1784** ⬆ | 900–1300 | jetzt zu teuer (Lohn-Drift) |
| S2 3-Zi-Whg | 6589 | **7667** ⬆ | 6000–9000 | weiter im Bereich, etwas höher |
| S3 Fassade | 11557 | **Refusal** ❌ | 11000–17000 | "I'm sorry, but I cannot assist" |

## Was funktioniert

✅ **Tool-Registrierung** sauber: `factory.warm_factory()` ruft jetzt `register_pinta_tools()`, das `search_materials` in pytaskforce' globaler Registry einträgt. Idempotent.

✅ **Agent ruft das Tool tatsächlich auf** — z.B. S3: drei `search_materials`-Calls für Silikatfarbe, Algenentferner, Holzbeschichtung mit `region="DE"`.

✅ **Graceful Fallback bei leerer DB.** S2 notes: "Materialpreise sind marktübliche Richtwerte, da die Materialdatenbank keine Treffer geliefert hat." — der Agent erkennt explizit, dass kein Treffer kam, und nutzt die Faustregeln aus dem System-Prompt.

✅ **Tool-Schema ohne f-string-Drama**, ohne `requires_approval` (sonst hätte jedes Material-Lookup einen User-Approval-Dialog gebraucht).

## Was Probleme macht

❌ **S3 Refusal nach mehreren Tool-Calls.** "I'm sorry, but I cannot assist with that request." nach 6696 Tokens. Vermutung: Azure Content-Filter oder ein Prompt-Loop, ausgelöst durch wiederholte leere Tool-Returns. Reproduzierbar?

⚠ **S1 ist um Faktor 2 teurer geworden** (891 → 1784). Der Agent hat plötzlich 18h für Standard-Schlafzimmer-Streichen veranschlagt (Faustregel: 8-11h für 53.7 m² Streichfläche). Mögliche Ursache: längeres ReAct-Loop durch zusätzliches Tool, mehr Bedacht-Modus → konservativere Stunden.

⚠ **Tokens hochgegangen**: S1 von 8472 → 13749, S2 von 10764 → 38189. Weil das Tool aufgerufen wird (selbst bei leeren Returns) und der Agent länger reasonet.

## Strukturelle Erkenntnis

Das Tool ist nutzlos, solange `MaterialPrice`-Tabelle leer ist. Es kostet Tokens (Tool-Schema im Prompt + Aufruf-Overhead) ohne Gegenwert. **Bevor das Tool produktiv was bringt, muss die DB seeded sein** — z.B. via Skript, das aus Hersteller-Preislisten (Caparol, Alpina, Keim) Embeddings vorberechnet.

## Empfehlung

Für JETZT: `search_materials` im YAML lassen, ABER ohne DB-Seed wird der Agent meistens auf Faustregeln zurückgreifen. Sobald MaterialPrice geseedet ist, wird Iter 5 das eigentliche Versprechen einlösen (echte Hersteller-Preise statt LLM-Schätzung).

**Nächster konkreter Schritt:** Telegram-Bot scharf machen (siehe `backend/src/telegram/runner.py` + `scripts/run_telegram_bot.py`). search_materials-Tuning erst NACH erstem Maler-Test.
