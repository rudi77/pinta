# Iteration 1 — Maler-Meister-Bewertung der Baseline

Bewertet am 2026-05-02. Modell: gpt-4o-mini, kein RAG.

## Vergleichstabelle

| Szenario | Quick (€ brutto) | Multi-Turn (€) | Realistisch DE 2026 | Quick-Δ | Multi-Δ |
|----------|------------------|----------------|---------------------|---------|---------|
| S1 Schlafzimmer (54 m² Streichfläche) | **2618** ❌ | 1227 (netto, ohne MwSt!) | ~900-1300 brutto | +160% | +20% ✓ |
| S2 3-Zi-Wohnung (240 m² Streichfläche) | **2501** ❌ | 4725 (netto) | ~6000-9000 brutto | -58% | -21% ⚠ |
| S3 Fassade EFH (240 m² + Holzläden + Gerüst) | **3127** ❌ | 10380 (netto) | ~11000-17000 brutto | -74% | -13% ✓ |

## Hauptbefunde

### Quick-Path ist NICHT produktionsreif
Drei strukturelle Probleme:
1. **Flächen-Halluzination.** S2 nutzt durchgängig 78 m² (= Wohnfläche aus Eingabe) als Streichfläche, statt aus Wohnfläche auf Wand+Decke (240 m²) hochzurechnen. S3 verkürzt 17 m² Holzläden auf 8.64 m².
2. **Erratisches Pricing.** S1 = 50 €/m² für simples Streichen (Faktor 4 zu hoch). S3 = 5 €/m² Fassade (Faktor 5-7 zu niedrig). Keine konsistente Kalkulationsgrundlage.
3. **Gerüst-Position absurd.** S3: 500 € Pauschal für 240 m² × 2 Wochen Gerüst — Realität 1500-3000 €.

### Multi-Turn-Path ist verwendbar, aber mit Lücken
- **Stundensatz konsistent 55 €/h** — sinnvoll im DE-Markt
- **Plausible Lohnstunden** (12 / 80 / 144 h) — passt zur Komplexität
- **Material-Differenzierung gut** (Spachtel, Isoliergrund, Silikat)
- **ABER drei systematische Lücken:**
  1. **`total_amount` ist NETTO**, nicht brutto. Schema sagt "MwSt 19% berücksichtigen", LLM ignoriert das im Output. **Rechtsproblem für ein deutsches Angebot.**
  2. **Material-Mengen plausibilisiert nicht.** S3: 6 L Silikatfarbe für 240 m² — eine Faustregel (1 L pro 5 m²) würde 30+ L erfordern. Werte zu konservativ.
  3. **Vorarbeiten-Lohnstunden verteilen sich nicht sauber.** S2: 80 h für komplette 3-Zi-Renovierung mit Vorarbeiten ist knapp (Realität 100-130 h).

### Querschnitt
- **Schemas zwischen Quick und Multi-Turn sind inkonsistent** (Quick hat `subtotal/vat_amount/total_amount`, Multi-Turn hat `quote.total_amount`/`quote.material_cost` aber keine VAT-Felder)
- Beide Prompts haben **kein Plausibilitäts-Anker** für €/m² oder L/m²

## Top-3 Fixes für Iteration 1

| # | Fix | Wo | Wirkung |
|---|-----|----|---------|
| 1 | Multi-Turn-Schema um `subtotal/vat_amount/total_amount` erweitern, MwSt explizit ausweisen | `process_answers_and_generate_quote` System-Prompt | S1/S2/S3 Multi-Turn werden brutto-konform |
| 2 | Plausibilitätsregeln im Quick-Prompt: Wohnfläche → Wandfläche-Hochrechnung, Preisband €/m² | `generate_quick_quote` System-Prompt | Quick-Path wird wenigstens halbwegs verwendbar |
| 3 | Material-Verbrauchs-Faustregeln (L pro m²) in beiden Prompts | beide System-Prompts | Materialmengen plausibilisiert |

Bonus: Stundensatz-Default in Settings (statt LLM ratenzulassen, konsistent 55-60 €/h).
