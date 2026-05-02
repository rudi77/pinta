# Iteration 1 — Post-Fix Bilanz

## Vergleich Baseline vs Post-Fix (alles brutto, EUR)

| Szenario | Baseline Quick | Post-Fix Quick | Baseline Multi | Post-Fix Multi | Realistisch DE |
|----------|----------------|----------------|----------------|----------------|----------------|
| S1 Schlafzimmer | 2618 ❌ | **762** ✓ | 1227 (netto¹) | **741** ✓ | 900–1300 |
| S2 3-Zi-Whg | 2501 ❌ | **14997** ❌ | 4725 (netto¹) | **4123** ⚠ | 6000–9000 |
| S3 Fassade | 3127 ❌ | **13759** ✓ | 10380 (netto¹) | **11995** ✓ | 11000–17000 |

¹ Baseline-Multi gab Netto im total_amount aus (Bug 1). Post-Fix ist brutto.

## Was die Top-3-Fixes gebracht haben

✅ **MwSt-Ausweis** überall sauber (`subtotal/vat_amount/total_amount` getrennt). Output ist jetzt rechtskonform für DE-Angebote.

✅ **Flächen-Hochrechnung** funktioniert. S1 Quick notiert wörtlich: "Streichfläche berechnet mit 3.4 × Wohnfläche" — die Faustregel wurde übernommen. S2 Quick: 78 m² Wohn → 265 m² Streich (78 × 3.4).

✅ **Material-Mengen plausibel.** S3 Multi: Silikatfarbe von 6 L auf 80 L gestiegen — endlich passt es zur 240 m²-Fassade.

✅ **Konsistenz zwischen Quick und Multi-Turn deutlich verbessert.** S1: 762/741 (~3% Differenz statt vorher Faktor 2). S3: 13759/11995 (~13% statt vorher Faktor 3).

## Was noch ein Problem bleibt

### S2 Quick (14997 €) — Doppelzählung von Vorarbeiten
Das LLM hat die Plausibility-Regel "25–40 €/m² mit umfangreichen Vorarbeiten" als ZWEI Positionen interpretiert:
- Position 1: "Vorarbeiten 265 m² × 30 €" = 7950 €
- Position 2: "Wände streichen 265 m² × 12 €" = 3180 €
→ Vorarbeiten werden separat zu €/m²-Tarif AUFGESCHLAGEN statt im Pauschaltarif enthalten.

**Fix für Iter 2:** Plausibility-Regel umformulieren: "Die €/m²-Tarife sind GESAMTPREISE (Lohn+Material+Vorarbeiten). Vorarbeiten dürfen NICHT als separate €/m²-Position addiert werden, höchstens als Pauschalaufschlag oder Zeit-Position."

### Multi-Turn unterschätzt Lohnstunden
- S1 Multi: 10 h für Schlafzimmer (realistisch 12–16 h)
- S2 Multi: 60 h für komplette 3-Zi-Whg mit Vorarbeiten (realistisch 90–120 h)
→ Liefert systematisch ~20–30 % zu wenig.

**Fix für Iter 2:** Lohn-Faustregel im Prompt: "Standard-Innenraumstreichen: 1 Maler schafft 5–7 m² pro Stunde. Mit umfangreichen Vorarbeiten: 3–4 m²/h."

### S3 Quick: Holzläden-Quadratmeter immer noch halluziniert
Input: "12 Holzfensterläden je 1.2 m × 0.6 m" → 8.64 m² statt der vorgegebenen 17 m² (im Input stand `17 m² Holzfläche gesamt`). LLM rechnet selbst aus statt Input-Wert zu nehmen.

## MVP-Reife-Einschätzung

**Multi-Turn-Pfad ist jetzt bedingt MVP-reif:**
- Konsistenter 55 €/h Stundensatz
- Brutto-Ausweis korrekt
- Plausible Material-Mengen
- Strukturell saubere Quote (4–6 Positionen, Notes mit Annahmen)
- Tendenz: 15–30 % zu konservativ kalkuliert
- **Geeignet als „Konzept-Entwurf, den der Maler nachprüft"** — NICHT als „abgegebene Quote ohne Review".

**Quick-Pfad teilweise reif:**
- S1, S3 jetzt im realistischen Bereich
- S2 hat noch den Doppelzählungs-Bug → eine weitere Iteration nötig

## Empfehlung

**Iteration 2 priorisieren:**
1. Plausibility-Regel präzisieren (Vorarbeiten-Doppelzählung)
2. Lohn-Geschwindigkeits-Faustregel (m²/h)
3. Input-Treue: LLM darf gegebene Mengenangaben nicht überschreiben

**Danach: das nächste Cluster aus der 5-Punkte-Schwachstellenliste angehen** (z.B. End-to-End-Flow oder Vertrauen/Nachvollziehbarkeit), oder: dieses Niveau als „v0.2-MVP für interne Maler-Tests" einfrieren und einen ersten Tester ranlassen.
