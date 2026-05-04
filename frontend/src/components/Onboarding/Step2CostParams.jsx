import React from 'react';
import { Input } from '../ui/input';
import { Button } from '../ui/button';
import { Label } from '../ui/label';

const Step2CostParams = ({ value, onChange, onBack, onNext }) => {
  const canContinue =
    Number(value.hourly_rate) > 0 && Number(value.material_cost_markup) >= 0;

  const handleSubmit = (e) => {
    e.preventDefault();
    if (canContinue) onNext();
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <h2 className="text-lg font-semibold">Deine Kalkulation</h2>
      <p className="text-sm text-gray-600">
        Diese Werte werden in jedes Angebot übernommen. Du kannst sie später in
        den Einstellungen ändern.
      </p>

      <div>
        <Label htmlFor="hourly_rate">Stundensatz (EUR / Stunde, netto)</Label>
        <Input
          id="hourly_rate"
          type="number"
          min="0"
          max="500"
          step="1"
          required
          value={value.hourly_rate}
          onChange={(e) =>
            onChange({ ...value, hourly_rate: e.target.value })
          }
        />
      </div>

      <div>
        <Label htmlFor="material_cost_markup">Materialaufschlag (%)</Label>
        <Input
          id="material_cost_markup"
          type="number"
          min="0"
          max="100"
          step="0.5"
          required
          value={value.material_cost_markup}
          onChange={(e) =>
            onChange({ ...value, material_cost_markup: e.target.value })
          }
        />
        <p className="text-xs text-gray-500 mt-1">
          Üblich sind 10–20 %.
        </p>
      </div>

      <div className="flex justify-between pt-2">
        <Button type="button" variant="outline" onClick={onBack}>
          Zurück
        </Button>
        <Button type="submit" disabled={!canContinue}>
          Weiter
        </Button>
      </div>
    </form>
  );
};

export default Step2CostParams;
