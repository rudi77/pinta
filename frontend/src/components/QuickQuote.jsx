import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import apiClient from '../services/apiClient';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Textarea } from './ui/textarea';
import { Label } from './ui/label';
import { Separator } from './ui/separator';

const QuickQuote = () => {
  const { user } = useAuth();
  const navigate = useNavigate();

  // Form state
  const [customerName, setCustomerName] = useState('');
  const [serviceDescription, setServiceDescription] = useState('');
  const [area, setArea] = useState('');
  const [additionalInfo, setAdditionalInfo] = useState('');

  // Result state
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [copied, setCopied] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!serviceDescription.trim()) return;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await apiClient.createQuickQuote({
        customer_name: customerName || undefined,
        service_description: serviceDescription,
        area: area || undefined,
        additional_info: additionalInfo || undefined,
      });
      setResult(response);
    } catch (err) {
      setError(err.message || 'Fehler bei der Angebotserstellung');
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = () => {
    if (!result) return;

    const lines = [
      `KOSTENVORANSCHLAG ${result.quote_number}`,
      `${result.project_title}`,
      '',
      ...(customerName ? [`Kunde: ${customerName}`, ''] : []),
      'Pos. | Beschreibung | Menge | Einheit | Einzelpreis | Gesamt',
      '-'.repeat(70),
      ...result.items.map(
        (item) =>
          `${item.position}. | ${item.description} | ${item.quantity} | ${item.unit} | ${item.unit_price.toFixed(2)} EUR | ${item.total_price.toFixed(2)} EUR`
      ),
      '-'.repeat(70),
      `Netto: ${result.subtotal.toFixed(2)} EUR`,
      `MwSt (19%): ${result.vat_amount.toFixed(2)} EUR`,
      `GESAMT: ${result.total_amount.toFixed(2)} EUR`,
      '',
      result.notes ? `Hinweise: ${result.notes}` : '',
      ...(result.recommendations?.length
        ? ['', 'Empfehlungen:', ...result.recommendations.map((r) => `- ${r}`)]
        : []),
    ];

    navigator.clipboard.writeText(lines.join('\n'));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownloadPdf = async () => {
    if (!result) return;
    let url = null;
    try {
      const { blob } = await apiClient.fetchAgentPdfByQuoteId(result.quote_id);
      url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${result.quote_number}.pdf`;
      a.click();
    } catch (err) {
      setError(err.message || 'PDF konnte nicht erzeugt werden');
    } finally {
      if (url) URL.revokeObjectURL(url);
    }
  };

  const handleReset = () => {
    setResult(null);
    setError(null);
    setCustomerName('');
    setServiceDescription('');
    setArea('');
    setAdditionalInfo('');
  };

  const formatCurrency = (value) => {
    return new Intl.NumberFormat('de-DE', {
      style: 'currency',
      currency: 'EUR',
    }).format(value);
  };

  // --- RESULT VIEW ---
  if (result) {
    return (
      <div className="min-h-screen bg-gray-50">
        <header className="bg-white shadow-sm border-b sticky top-0 z-10">
          <div className="container mx-auto px-4 py-4 flex justify-between items-center">
            <h1 className="text-xl font-bold text-gray-900">Maler Kostenvoranschlag</h1>
            <div className="flex items-center space-x-3">
              <Button variant="outline" onClick={() => navigate('/dashboard')}>
                Dashboard
              </Button>
              <span className="text-sm text-gray-600">
                {user?.username || user?.company_name || 'User'}
              </span>
            </div>
          </div>
        </header>

        <main className="container mx-auto px-4 py-8 max-w-3xl">
          <Card>
            <CardHeader>
              <div className="flex justify-between items-start">
                <div>
                  <CardTitle className="text-2xl">{result.project_title}</CardTitle>
                  <p className="text-sm text-gray-500 mt-1">{result.quote_number}</p>
                  {customerName && (
                    <p className="text-sm text-gray-600 mt-1">Kunde: {customerName}</p>
                  )}
                </div>
                <div className="text-right">
                  <p className="text-3xl font-bold text-green-700">
                    {formatCurrency(result.total_amount)}
                  </p>
                  <p className="text-xs text-gray-500">inkl. MwSt.</p>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {/* Items Table */}
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b bg-gray-50">
                      <th className="text-left py-2 px-2 font-medium">Pos.</th>
                      <th className="text-left py-2 px-2 font-medium">Beschreibung</th>
                      <th className="text-right py-2 px-2 font-medium">Menge</th>
                      <th className="text-left py-2 px-2 font-medium">Einheit</th>
                      <th className="text-right py-2 px-2 font-medium">Einzelpreis</th>
                      <th className="text-right py-2 px-2 font-medium">Gesamt</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.items.map((item, index) => (
                      <tr key={index} className="border-b">
                        <td className="py-2 px-2 text-gray-500">{item.position}</td>
                        <td className="py-2 px-2">{item.description}</td>
                        <td className="py-2 px-2 text-right">{item.quantity}</td>
                        <td className="py-2 px-2">{item.unit}</td>
                        <td className="py-2 px-2 text-right">{formatCurrency(item.unit_price)}</td>
                        <td className="py-2 px-2 text-right font-medium">
                          {formatCurrency(item.total_price)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Totals */}
              <div className="mt-4 border-t pt-4 space-y-1">
                <div className="flex justify-between text-sm">
                  <span>Netto</span>
                  <span>{formatCurrency(result.subtotal)}</span>
                </div>
                <div className="flex justify-between text-sm text-gray-600">
                  <span>MwSt. (19%)</span>
                  <span>{formatCurrency(result.vat_amount)}</span>
                </div>
                <Separator />
                <div className="flex justify-between text-lg font-bold">
                  <span>Gesamtbetrag</span>
                  <span className="text-green-700">{formatCurrency(result.total_amount)}</span>
                </div>
              </div>

              {/* Notes */}
              {result.notes && (
                <div className="mt-6 p-3 bg-blue-50 rounded-lg">
                  <p className="text-sm font-medium text-blue-800 mb-1">Hinweise</p>
                  <p className="text-sm text-blue-700">{result.notes}</p>
                </div>
              )}

              {/* Recommendations */}
              {result.recommendations?.length > 0 && (
                <div className="mt-4 p-3 bg-amber-50 rounded-lg">
                  <p className="text-sm font-medium text-amber-800 mb-1">Empfehlungen</p>
                  <ul className="text-sm text-amber-700 list-disc list-inside">
                    {result.recommendations.map((rec, i) => (
                      <li key={i}>{rec}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Action Buttons */}
              <div className="mt-8 flex flex-wrap gap-3">
                <Button onClick={handleCopy} variant="default" className="flex-1 min-w-[140px]">
                  {copied ? 'Kopiert!' : 'Angebot kopieren'}
                </Button>
                <Button
                  onClick={handleDownloadPdf}
                  variant="outline"
                  className="flex-1 min-w-[140px]"
                >
                  PDF herunterladen
                </Button>
                <Button onClick={handleReset} variant="outline" className="flex-1 min-w-[140px]">
                  Neues Angebot
                </Button>
              </div>
            </CardContent>
          </Card>
        </main>
      </div>
    );
  }

  // --- FORM VIEW ---
  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow-sm border-b sticky top-0 z-10">
        <div className="container mx-auto px-4 py-4 flex justify-between items-center">
          <h1 className="text-xl font-bold text-gray-900">Maler Kostenvoranschlag</h1>
          <div className="flex items-center space-x-3">
            <Button variant="outline" onClick={() => navigate('/dashboard')}>
              Dashboard
            </Button>
            <span className="text-sm text-gray-600">
              {user?.username || user?.company_name || 'User'}
            </span>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8 max-w-2xl">
        <Card>
          <CardHeader>
            <CardTitle className="text-2xl">Schnell-Angebot erstellen</CardTitle>
            <p className="text-sm text-gray-500">
              Beschreibe die Arbeit und erhalte in Sekunden ein professionelles Angebot.
            </p>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-5">
              <div>
                <Label htmlFor="customerName">Kundenname (optional)</Label>
                <Input
                  id="customerName"
                  value={customerName}
                  onChange={(e) => setCustomerName(e.target.value)}
                  placeholder="z.B. Familie Müller"
                  className="mt-1"
                />
              </div>

              <div>
                <Label htmlFor="serviceDescription">
                  Was soll gemacht werden? <span className="text-red-500">*</span>
                </Label>
                <Textarea
                  id="serviceDescription"
                  value={serviceDescription}
                  onChange={(e) => setServiceDescription(e.target.value)}
                  placeholder="z.B. Wohnzimmer streichen, 3 Wände weiß, 1 Akzentwand in Anthrazit. Decke ebenfalls weiß streichen."
                  rows={4}
                  required
                  className="mt-1"
                />
              </div>

              <div>
                <Label htmlFor="area">Fläche / Umfang (optional)</Label>
                <Input
                  id="area"
                  value={area}
                  onChange={(e) => setArea(e.target.value)}
                  placeholder="z.B. ca. 45m², 3 Zimmer, Altbauwohnung 80m²"
                  className="mt-1"
                />
              </div>

              <div>
                <Label htmlFor="additionalInfo">Zusatzinfos (optional)</Label>
                <Textarea
                  id="additionalInfo"
                  value={additionalInfo}
                  onChange={(e) => setAdditionalInfo(e.target.value)}
                  placeholder="z.B. Altbau mit hohen Decken (3,20m), alte Tapete muss entfernt werden, Stuckleisten vorhanden"
                  rows={3}
                  className="mt-1"
                />
              </div>

              {error && (
                <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
                  {error}
                </div>
              )}

              <Button type="submit" disabled={loading || !serviceDescription.trim()} className="w-full text-lg py-6">
                {loading ? (
                  <span className="flex items-center justify-center gap-2">
                    <svg
                      className="animate-spin h-5 w-5"
                      viewBox="0 0 24 24"
                      fill="none"
                    >
                      <circle
                        className="opacity-25"
                        cx="12"
                        cy="12"
                        r="10"
                        stroke="currentColor"
                        strokeWidth="4"
                      />
                      <path
                        className="opacity-75"
                        fill="currentColor"
                        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                      />
                    </svg>
                    Angebot wird erstellt...
                  </span>
                ) : (
                  'Angebot erstellen'
                )}
              </Button>
            </form>
          </CardContent>
        </Card>
      </main>
    </div>
  );
};

export default QuickQuote;
