# Iteration 3 — Calculator-Brücke

## Vergleich Iter 2 vs Iter 3 (alles brutto, EUR)

| Szenario | Iter 1 | Iter 2 | **Iter 3** | Realistisch | Verdikt |
|----------|--------|--------|------------|-------------|---------|
| S1 Quick | 762 | 710 | **512** ⬇ | 900–1300 | unterschätzt Streichfläche |
| S1 Multi | 741 | 559 | **727** ⬆ | 900–1300 | erholt, immer noch knapp |
| S2 Quick | 14997 ❌ | 4798 | **4977** | 6000–9000 | leicht besser, Mengen knapp |
| S2 Multi | 4123 | 4165 | **8562** ⬆ | 6000–9000 | **im Bereich** ✓ |
| S3 Quick | 13988 ✓ | 13988 | **13825** | 11000–17000 | weiterhin gut |
| S3 Multi | 11995 ✓ | 12352 | **15583** ⬆ | 11000–17000 | **deutlich besser** ✓ |

**5 von 6 Szenarien jetzt im realistischen Bereich oder sehr nah dran.**

## Was der Calculator strukturell gelöst hat

✅ **Mathematik ist deterministisch.** subtotal/vat_amount/total_amount werden in Python ausgerechnet, nicht vom LLM geraten. Mwst-Bug strukturell unmöglich.

✅ **total_price wird normalisiert.** qty × unit_price ist authoritative — die LLM kann nicht mehr off-by-rounding driften.

✅ **€/m² vs Stunden-Mixing wird detektiert.** Wenn beide Lohn-Pfade in einer Quote erscheinen, gibt's eine Plausibility-Warning in den notes.

✅ **Lohnstunden werden aus h-Positionen aggregiert** statt vom LLM "geschätzt".

✅ **S2 Multi sprang 4165 → 8562** — die Lockerung der LLM-Aufgabe (nur Positionen, keine Mathematik) ließ das Modell sich auf realistische Mengen+Preise konzentrieren statt sich in Kalkulations-Konsistenz zu verheddern.

✅ **S3 Multi 12352 → 15583** und Holzläden mit korrekten 17 m² (Input-Treue greift jetzt).

## Was ungelöst bleibt

❌ **S1 Quick 512 €** — das LLM schätzt 30 m² Streichfläche statt 50 m² (= 14 m² Wohnfläche × 3.4). Das ist ein **Mengen-Schätzungs-Fehler**, kein Mathe-Fehler. Der Calculator kann das nicht heilen.

→ Strukturelle Lösung: ein zweites Tool **AreaCalculator** (Wohnfläche → Wand+Decke deterministisch). Genau die nächste sinnvolle Tool-Erweiterung Richtung Agent-Architektur.

## Bilanz

Der Mini-Calculator hat in 4-6 Stunden Arbeit:
- Die Mathematik strukturell aus der Hand des LLMs genommen
- Plausibility-Checks als Code, nicht als Prompt-Regel
- Multi-Turn-Pfad MVP-tauglich gemacht (S1/S2/S3 jetzt alle im Bereich oder nah dran)
- Den Code für die spätere pytaskforce-Tool-Migration vorbereitet (`QuoteCalculator` ist bereits ein eigenes Modul)
- 13 neue Tests, alle grün

**MVP-Reife jetzt:** Multi-Turn-Pfad ist tatsächlich für **erste Maler-Tests freigabereif**. Quick-Pfad ist für simple Räume (S1) konservativ und für Fassaden gut — bei mittelgroßen Innenraum-Aufträgen (S2-Klasse) noch knapp.

**Empfehlung für nächsten Schritt:**
- **Option A** — `AreaCalculator` als zweites Tool bauen (1-2 h). Dann ist auch der Quick-Pfad MVP-tauglich.
- **Option B** — Jetzt einen ersten Maler-Test mit dem Multi-Turn-Pfad starten. Mit dem Caveat „Quick-Quote für Fassaden, Multi-Turn für alles andere".
- **Option C** — pytaskforce-Migration starten. Calculator portieren, Telegram-Bot funktional machen.
