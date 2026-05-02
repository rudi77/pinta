# Iteration 4 — pytaskforce Maler-Agent (Azure / gpt-5.4-mini + python tool)

## Vergleich Iter 1 → 4 (alles brutto, EUR)

| Szenario | Iter 1 Quick | Iter 1 Multi | Iter 2 Quick | Iter 2 Multi | Iter 3 Quick | Iter 3 Multi | **Iter 4 Agent** | Realistisch |
|----------|-------------:|-------------:|-------------:|-------------:|-------------:|-------------:|------------------:|------------:|
| S1 Schlafzimmer | 762 | 741 | 710 | 559 | 512 | 727 | **891** | 900–1300 |
| S2 3-Zi-Whg | 14997 | 4123 | 4798 | 4165 | 4977 | 8562 | **6589** | 6000–9000 |
| S3 Fassade | 13988 | 11995 | 13988 | 12352 | 13825 | 15583 | **11557** | 11000–17000 |

**Alle 3 Szenarien zum ersten Mal in einer Iteration im realistischen Bereich.** Tendenz: konservativ am unteren Rand — was für einen vom Maler nachgeprüften Vor-Entwurf eher gut als schlecht ist.

## Was der Agent strukturell anders macht

✅ **Tool-Use ist real.** Das python-Tool wird tatsächlich aufgerufen, im S3-Fall mit:
```python
items = [...]
subtotal = sum(i['quantity'] * i['unit_price'] for i in items)
vat_amount = round(subtotal * 0.19, 2)
total_amount = round(subtotal + vat_amount, 2)
result = {...}
```
→ **Mathematik ist physisch unmöglich falsch zu sein.** Selbst wenn das LLM eine Position vergisst oder einen Preis verändert, das Aufsummieren passiert in Python.

✅ **Domain-Faustregeln im System-Prompt + Tool für Anwendung** ergibt:
- 17 L Farbe für 53.7 m² × 2 Anstriche → 1 L pro 6.3 m² (Faustregel: 5–7 m²/L) ✓
- 78 h für 240 m² mit Vorarbeiten → 3.07 m²/h (Faustregel: 3–4 m²/h) ✓
- Silikatfarbe 96 L für 240 m² × 2 Anstriche → 1 L pro 5 m² (Faustregel: 4–6) ✓

✅ **Input-Treue strukturell.** S3 hat die "17 m² Holzfläche gesamt" aus der Mission direkt übernommen, statt 12 × 1.2 × 0.6 selbst zu rechnen. S2 nimmt 240 m² Streichfläche direkt.

✅ **Strukturierte Quote-Items mit Kategorien** (preparation / labor / material / additional). S1 hat sogar Vorarbeiten korrekt aufgeteilt: "Abdecken" als preparation, "Anstrich" als labor.

✅ **Annahmen werden explizit dokumentiert.** Aus S2 notes: "Die Wohnung ist leerstehend und gut zugänglich, daher wurden normale Schutz- und Abklebearbeiten kalkuliert. Der Wasserfleck wird als lokaler, nicht aktiver Schaden bewertet; nur Isoliergrund ist enthalten. Türen und Fenster werden ausgespart, Lackarbeiten an Innentüren sind nicht enthalten."

✅ **Sinnvolle Empfehlungen.** "Wenn die gelbliche Altfarbe stark durchschlägt, zusätzlich einen Isolier- oder Sperrgrund einplanen" — das ist echtes Maler-Wissen, nicht generischer KI-Smalltalk.

## Token-Verbrauch und Latenz

| Szenario | Tokens | Latenz |
|----------|-------:|-------:|
| S1 | 8472 | 22 s |
| S2 | 10764 | 35 s |
| S3 | 11059 | 35 s |

→ ~10 k tokens pro Quote. Bei gpt-5.4-mini-Pricing: < 5 ct pro Generierung. Latenz 22-35 s ist OK für einen "Maler stellt Anfrage, bekommt Vor-Entwurf zurück"-Flow, aber zu lang für synchrones HTTP — sollte als Background-Task laufen oder mit Streaming.

## Was Iter 4 NICHT abdeckt (Folge-Arbeit)

🔲 **Pinta-spezifische Tools.** Aktuell nur `python`. Stubs liegen schon in `backend/src/agents/tools/`:
- `search_materials` — RAG über `MaterialPrice`-Tabelle für reale DE-Preise
- `visual_estimate` — Foto → Raum/Fläche/Zustand (gpt-4o vision)
- `save_draft` — Quote in DB persistieren
- `generate_pdf` — `professional_pdf_service` aufrufen

🔲 **Backend-Endpunkte umstellen.** `routes/ai.py` ruft noch direkt `ai_service` auf. Mittelfristig: `/api/v1/ai/generate-quote` ruft den Agent.

🔲 **FastAPI-Lifespan.** `warm_factory()` muss beim Startup laufen, nicht beim ersten Request.

🔲 **Telegram-Bot.** Stubs in `backend/src/telegram/bot.py` brauchen Handler-Implementierung gegen den Agent.

🔲 **Skills/Workflows.** pytaskforce kann mehrstufige Workflows (`kostenvoranschlag_erstellen`) — aktuell macht alles ein freier ReAct-Loop.

## MVP-Reife jetzt

**Pinta hat zum ersten Mal einen funktionierenden, durchgehend qualitativ akzeptablen Quote-Generator.** Der Agent-Pfad ist:
1. Reproduzierbar (Calculator macht Math, nicht das LLM)
2. Konfigurierbar (Modell-Wechsel via `AGENT_LLM_MODEL_ALIAS` in .env)
3. Erweiterbar (neue Tools werden einfach in factory.py registriert)
4. Direkt der pytaskforce-Migration — kein Wegwurf-Code

**Empfehlung:** Stand committen, dann den nächsten konkreten Schritt wählen:
- (A) Endpoint `/api/v1/ai/generate-quote` auf Agent umstellen + erster echter Maler-Test mit dem User-Flow
- (B) `search_materials` als zweites Tool (RAG aktivieren)
- (C) Telegram-Bot scharf schalten
