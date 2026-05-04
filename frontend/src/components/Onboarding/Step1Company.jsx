import React from 'react';
import { Input } from '../ui/input';
import { Button } from '../ui/button';
import { Label } from '../ui/label';

const Step1Company = ({ value, onChange, onNext }) => {
  const canContinue =
    value.company_name.trim().length >= 2 && value.address.trim().length >= 2;

  const handleSubmit = (e) => {
    e.preventDefault();
    if (canContinue) onNext();
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <h2 className="text-lg font-semibold">Dein Betrieb</h2>

      <div>
        <Label htmlFor="company_name">Firmenname</Label>
        <Input
          id="company_name"
          type="text"
          required
          value={value.company_name}
          onChange={(e) => onChange({ ...value, company_name: e.target.value })}
          placeholder="Maler Müller GmbH"
        />
      </div>

      <div>
        <Label htmlFor="address">Anschrift</Label>
        <Input
          id="address"
          type="text"
          required
          value={value.address}
          onChange={(e) => onChange({ ...value, address: e.target.value })}
          placeholder="Hauptstraße 1, 1010 Wien"
        />
      </div>

      <div>
        <Label htmlFor="vat_id">USt-Nr. (optional)</Label>
        <Input
          id="vat_id"
          type="text"
          value={value.vat_id}
          onChange={(e) => onChange({ ...value, vat_id: e.target.value })}
          placeholder="ATU12345678"
        />
      </div>

      <div className="flex justify-end pt-2">
        <Button type="submit" disabled={!canContinue}>
          Weiter
        </Button>
      </div>
    </form>
  );
};

export default Step1Company;
