# Iteration 2 — Bilanz

## Vergleich Iter 1 vs Iter 2 (alles brutto, EUR)

| Szenario | Iter 1 | Iter 2 | Realistisch | Verdikt |
|----------|--------|--------|-------------|---------|
| S1 Quick | 762 | **710** | 900–1300 | leicht zurück, ~30% knapp |
| S1 Multi | 741 | **559** ⬇ | 900–1300 | **Verschlechterung — Side-Effect** |
| S2 Quick | 14997 ❌ | **4798** ✓ | 6000–9000 | **Doppelzählung gefixt** |
| S2 Multi | 4123 | **4165** | 6000–9000 | unverändert |
| S3 Quick | 13759 ✓ | **13988** ✓ | 11000–17000 | im Bereich |
| S3 Multi | 11995 ✓ | **12352** ✓ | 11000–17000 | im Bereich |

## Was Iter 2 erreicht hat

✅ **S2 Quick Doppelzählung-Bug ist weg.** Vorarbeiten werden jetzt als Pauschalposition (300 €) ausgewiesen statt als zusätzlicher €/m²-Tarif. Die Plausibility-Regel-Klarstellung ("Tarife sind GESAMTPREISE, NICHT additiv kombinieren") hat gegriffen.

✅ **S3 stabil gut** in beiden Pfaden.

## Was Iter 2 als Side-Effect produziert hat

❌ **S1 Multi-Turn ist schlechter geworden** (741 → 559). Ursache: Das LLM mischt jetzt im Multi-Turn-Pfad die €/m²-Pauschalen statt konsequent Stunden × Stundensatz zu rechnen.

S1 Multi Iter 1 (gut):
- "Arbeitszeit Maler 12 h × 55 € = 660 €" ← Stunden-basiert
- + Material 180 € → ~1227 € netto

S1 Multi Iter 2 (schwächer):
- "Streichen Wände+Decke 53.7 m² × 8 €/m² = 430 €" ← €/m²-Pauschal
- + Material 120 € → 559 € brutto

Die Lohn-m²/h-Faustregel ("5–7 m²/h Standard") wurde nicht ergriffen — das LLM hat stattdessen die €/m²-Pauschalregel als Komplett-Tarif für die Lohn-Position interpretiert.

⚠ **S2 Multi unverändert schlecht** (4165 € statt 6000–9000). LLM nimmt 70 h × 50 €/h = 3500 € — Stundenzahl wäre korrekt nach m²/h-Regel (240 m² ÷ 3.4 m²/h ≈ 70h), aber das LLM nutzt einen sehr niedrigen Stundensatz (50 € statt 55–65 €) und rechnet das Material zu konservativ.

## Strukturelle Erkenntnis

Die Plausibility-Regeln in EINEM gemeinsamen Prompt-Block, der zwei Pfade bedient (Quick + Multi-Turn), erzeugt Konflikte:
- Quick-Path braucht **€/m²-Pauschalen** (schnell, grob, Lohn+Material kombiniert)
- Multi-Path braucht **Stunden-Kalkulation** (detailliert, getrennt, mit Material-Mengen)

Die kombinierte Regel-Sammlung verleitet das LLM zur Mischung beider Modi.

## Drei Wege ab hier

1. **Iter 3 — Path-Differenzierung im Prompt.** Quick-Prompt bekommt nur die €/m²-Regeln, Multi-Prompt nur die Stunden-Regeln. Schnell zu implementieren, ein weiterer Tuning-Schritt.
2. **Stop und einfrieren.** S3 ist bereits MVP-tauglich. S1 ist im Bereich. Nur S2 ist noch problematisch. Mit dem Caveat "Multi-Turn-Output ist konservativ kalkuliert, Maler prüft selbst" könnte das v0.2-MVP-Niveau für interne Tests sein.
3. **Strategiewechsel — pytaskforce-Agent-Migration starten.** Das ursprüngliche Architekturziel: Tools (Calculator, Materialdatenbank) statt Prompt-Akrobatik. Würde die strukturellen Konflikte (Path-Differenzierung, Konsistenz Quick↔Multi, Lohn-vs-€/m²) deterministisch lösen.

## Empfehlung

**Option 3 ist der eigentliche Plan** (siehe Memory `Pinta Agent-Architektur-Strategie`). Weiteres Prompt-Tuning hat abnehmenden Grenznutzen — je mehr Regeln in den Prompt, desto mehr Mischungs-Konflikte. Ein Calculator-Tool würde "240 m² × 35 €/m² + MwSt 19%" deterministisch ausrechnen, statt das LLM raten zu lassen.

Iter 3 würde noch ~10–20 % Genauigkeit bringen, kostet ~30 Minuten. Agent-Migration ist die größere Investition mit deutlich höherer Decke.
