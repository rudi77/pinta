import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import apiClient from '../services/apiClient';
import { Button } from './ui/button';
import { Card } from './ui/card';

const QuoteDetail = () => {
  const { quoteId } = useParams();
  const navigate = useNavigate();
  const [quote, setQuote] = useState(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    const loadQuote = async () => {
      try {
        const data = await apiClient.getQuote(quoteId);
        setQuote(data);
      } catch {
        setError('Fehler beim Laden des Angebots');
      } finally {
        setLoading(false);
      }
    };

    loadQuote();
  }, [quoteId]);

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('de-DE', {
      style: 'currency',
      currency: 'EUR'
    }).format(amount);
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('de-DE', {
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    });
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'accepted':
        return 'bg-green-100 text-green-800';
      case 'pending':
        return 'bg-yellow-100 text-yellow-800';
      case 'rejected':
        return 'bg-red-100 text-red-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const getStatusText = (status) => {
    switch (status) {
      case 'accepted':
        return 'Angenommen';
      case 'pending':
        return 'Ausstehend';
      case 'rejected':
        return 'Abgelehnt';
      case 'draft':
        return 'Entwurf';
      default:
        return status;
    }
  };

  const handleDownloadPdf = async () => {
    if (!quote) return;
    setActionLoading(true);
    setError(null);
    let url = null;
    try {
      const { blob } = await apiClient.fetchAgentPdfByQuoteId(quote.id);
      url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `${quote.quote_number}.pdf`;
      link.click();
    } catch (err) {
      setError(err.message || 'PDF konnte nicht erzeugt werden');
    } finally {
      if (url) URL.revokeObjectURL(url);
      setActionLoading(false);
    }
  };

  const handleDuplicate = async () => {
    if (!quote) return;
    setActionLoading(true);
    setError(null);
    try {
      const duplicatedQuote = await apiClient.duplicateQuote(quote.id);
      navigate(`/quotes/${duplicatedQuote.id}`);
    } catch (err) {
      setError(err.message || 'Angebot konnte nicht dupliziert werden');
    } finally {
      setActionLoading(false);
    }
  };

  const handleStatusChange = async (e) => {
    const nextStatus = e.target.value;
    if (!quote || nextStatus === quote.status) return;
    setActionLoading(true);
    setError(null);
    try {
      const updatedQuote = await apiClient.updateQuoteStatus(quote, nextStatus);
      setQuote(updatedQuote);
    } catch (err) {
      setError(err.message || 'Status konnte nicht geändert werden');
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-600"></div>
      </div>
    );
  }

  if (error && !quote) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen">
        <p className="text-red-600 mb-4">{error}</p>
        <Button onClick={() => navigate('/dashboard')}>Zurück zum Dashboard</Button>
      </div>
    );
  }

  if (!quote) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen">
        <p className="text-gray-600 mb-4">Angebot nicht gefunden</p>
        <Button onClick={() => navigate('/dashboard')}>Zurück zum Dashboard</Button>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="mb-6 flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Angebot {quote.quote_number}</h1>
        <div className="flex flex-wrap gap-2">
          <Button onClick={handleDownloadPdf} disabled={actionLoading}>
            PDF herunterladen
          </Button>
          <Button variant="outline" onClick={() => navigate('/quote/new')} disabled={actionLoading}>
            Neues Angebot
          </Button>
          <Button variant="outline" onClick={handleDuplicate} disabled={actionLoading}>
            Duplizieren
          </Button>
          <select
            aria-label="Status ändern"
            value={quote.status}
            onChange={handleStatusChange}
            disabled={actionLoading}
            className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm"
          >
            <option value="draft">Entwurf</option>
            <option value="pending">Ausstehend</option>
            <option value="accepted">Angenommen</option>
            <option value="rejected">Abgelehnt</option>
          </select>
          <Button variant="outline" onClick={() => navigate('/dashboard')}>Zurück zum Dashboard</Button>
        </div>
      </div>

      {error && (
        <div className="mb-6 rounded border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        <Card className="p-6">
          <h2 className="text-lg font-semibold mb-4">Kundeninformationen</h2>
          <div className="space-y-2">
            <p><span className="font-medium">Name:</span> {quote.customer_name}</p>
            <p><span className="font-medium">E-Mail:</span> {quote.customer_email}</p>
            <p><span className="font-medium">Telefon:</span> {quote.customer_phone}</p>
            <p><span className="font-medium">Adresse:</span> {quote.customer_address}</p>
          </div>
        </Card>

        <Card className="p-6">
          <h2 className="text-lg font-semibold mb-4">Projektinformationen</h2>
          <div className="space-y-2">
            <p><span className="font-medium">Titel:</span> {quote.project_title}</p>
            <p><span className="font-medium">Beschreibung:</span> {quote.project_description}</p>
            <p><span className="font-medium">Status:</span> 
              <span className={`ml-2 inline-flex px-2 py-1 text-xs font-semibold rounded-full ${getStatusColor(quote.status)}`}>
                {getStatusText(quote.status)}
              </span>
            </p>
            <p><span className="font-medium">Erstellt am:</span> {formatDate(quote.created_at)}</p>
          </div>
        </Card>
      </div>

      <Card className="p-6 mb-8">
        <h2 className="text-lg font-semibold mb-4">Angebotspositionen</h2>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Position</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Beschreibung</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Menge</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Einheit</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Einzelpreis</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Gesamtpreis</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {quote.items.map((item) => (
                <tr key={item.id}>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{item.position}</td>
                  <td className="px-6 py-4 text-sm text-gray-900">{item.description}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{item.quantity}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{item.unit}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{formatCurrency(item.unit_price)}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{formatCurrency(item.total_price)}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="bg-gray-50">
                <td colSpan="5" className="px-6 py-4 text-right text-sm font-medium text-gray-900">Gesamtbetrag:</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{formatCurrency(quote.total_amount)}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      </Card>

      {quote.conversation_history && quote.conversation_history.length > 0 && (
        <Card className="p-6">
          <h2 className="text-lg font-semibold mb-4">Chat-Verlauf</h2>
          <div className="space-y-4">
            {quote.conversation_history.map((msg, index) => (
              <div key={index} className={`p-4 rounded-lg ${msg.role === 'assistant' ? 'bg-purple-50' : 'bg-gray-50'}`}>
                <p className="font-medium mb-2">{msg.role === 'assistant' ? 'Pinta' : 'Du'}</p>
                <p className="text-gray-700">{msg.content}</p>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
};

export default QuoteDetail; 