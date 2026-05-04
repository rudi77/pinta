import React, { useState } from 'react';
import { Card } from '../ui/card';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Button } from '../ui/button';
import apiClient from '../../services/apiClient';

const toNum = (val) => {
  const n = Number(val);
  return Number.isFinite(n) ? n : null;
};

const CostSection = ({ profile, onSaved }) => {
  const [form, setForm] = useState({
    hourly_rate: profile.hourly_rate ?? 45,
    material_cost_markup: profile.material_cost_markup ?? 15,
  });
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState(null);

  const canSave =
    toNum(form.hourly_rate) !== null &&
    toNum(form.hourly_rate) > 0 &&
    toNum(form.material_cost_markup) !== null &&
    toNum(form.material_cost_markup) >= 0;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!canSave) return;
    setSaving(true);
    setStatus(null);
    try {
      await apiClient.updateUserProfile({
        hourly_rate: toNum(form.hourly_rate),
        material_cost_markup: toNum(form.material_cost_markup),
      });
      setStatus({ type: 'ok', text: 'Kalkulationswerte gespeichert.' });
      await onSaved?.();
    } catch (err) {
      setStatus({ type: 'err', text: err.message || 'Speichern fehlgeschlagen' });
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card className="p-6">
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <h2 className="text-lg font-semibold">Kalkulation</h2>
          <p className="text-sm text-gray-600">
            Stundensatz und Materialaufschlag werden in jeder Kalkulation
            verwendet.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <Label htmlFor="hourly_rate">Stundensatz (EUR / Stunde, netto)</Label>
            <Input
              id="hourly_rate"
              type="number"
              min="0"
              max="500"
              step="1"
              value={form.hourly_rate}
              onChange={(e) =>
                setForm((p) => ({ ...p, hourly_rate: e.target.value }))
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
              value={form.material_cost_markup}
              onChange={(e) =>
                setForm((p) => ({ ...p, material_cost_markup: e.target.value }))
              }
            />
          </div>
        </div>

        <div className="flex items-center gap-3">
          <Button type="submit" disabled={!canSave || saving}>
            {saving ? 'Speichere…' : 'Speichern'}
          </Button>
          {status && (
            <span
              className={`text-sm ${
                status.type === 'ok' ? 'text-green-700' : 'text-red-600'
              }`}
            >
              {status.text}
            </span>
          )}
        </div>
      </form>
    </Card>
  );
};

export default CostSection;
