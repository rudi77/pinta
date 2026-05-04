import React, { useState } from 'react';
import { Card } from '../ui/card';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Button } from '../ui/button';
import apiClient from '../../services/apiClient';

const CompanySection = ({ profile, onSaved }) => {
  const [form, setForm] = useState({
    company_name: profile.company_name || '',
    address: profile.address || '',
    vat_id: profile.vat_id || '',
    phone: profile.phone || '',
  });
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState(null);

  const handleChange = (field) => (e) =>
    setForm((prev) => ({ ...prev, [field]: e.target.value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setStatus(null);
    try {
      await apiClient.updateUserProfile({
        company_name: form.company_name.trim() || null,
        address: form.address.trim() || null,
        vat_id: form.vat_id.trim() || null,
        phone: form.phone.trim() || null,
      });
      setStatus({ type: 'ok', text: 'Firmendaten gespeichert.' });
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
          <h2 className="text-lg font-semibold">Firmendaten</h2>
          <p className="text-sm text-gray-600">
            Erscheinen im Briefkopf jedes generierten Angebots.
          </p>
        </div>

        <div>
          <Label htmlFor="company_name">Firmenname</Label>
          <Input
            id="company_name"
            value={form.company_name}
            onChange={handleChange('company_name')}
            placeholder="Maler Müller GmbH"
          />
        </div>

        <div>
          <Label htmlFor="address">Anschrift</Label>
          <Input
            id="address"
            value={form.address}
            onChange={handleChange('address')}
            placeholder="Hauptstraße 1, 1010 Wien"
          />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <Label htmlFor="vat_id">USt-Nr.</Label>
            <Input
              id="vat_id"
              value={form.vat_id}
              onChange={handleChange('vat_id')}
              placeholder="ATU12345678"
            />
          </div>
          <div>
            <Label htmlFor="phone">Telefon</Label>
            <Input
              id="phone"
              value={form.phone}
              onChange={handleChange('phone')}
              placeholder="+43 1 1234567"
            />
          </div>
        </div>

        <div className="flex items-center gap-3">
          <Button type="submit" disabled={saving}>
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

export default CompanySection;
