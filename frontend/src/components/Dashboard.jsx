import React, { useState, useEffect } from 'react';
import { useAuth } from '../hooks/useAuth';
import apiClient from '../services/apiClient';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { useNavigate } from 'react-router-dom';

const Dashboard = ({ onNavigate }) => {
  const { user, demoMode } = useAuth();
  const [quotes, setQuotes] = useState([]);
  const [stats, setStats] = useState({
    totalQuotes: 0,
    thisMonth: 0,
    successRate: 0,
    totalRevenue: 0
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    const loadDashboardData = async () => {
      try {
        if (demoMode) {
          // Use mock data for demo mode
          setQuotes([
            {
              id: 1,
              quote_number: 'KV-20250606-001',
              customer_name: 'Familie Müller',
              project_title: 'Wohnzimmer Renovierung',
              total_amount: 2450.00,
              status: 'accepted',
              created_at: '2025-06-03T10:00:00Z'
            },
            {
              id: 2,
              quote_number: 'KV-20250606-002',
              customer_name: 'Firma Schmidt',
              project_title: 'Büro Anstrich',
              total_amount: 1890.00,
              status: 'pending',
              created_at: '2025-06-01T14:30:00Z'
            },
            {
              id: 3,
              quote_number: 'KV-20250606-003',
              customer_name: 'Familie Weber',
              project_title: 'Küche streichen',
              total_amount: 890.00,
              status: 'accepted',
              created_at: '2025-05-28T09:15:00Z'
            }
          ]);
          
          setStats({
            totalQuotes: 3,
            thisMonth: 3,
            successRate: 85,
            totalRevenue: 5230.00
          });
        } else {
          // Load real data from API
          const quotesData = await apiClient.getQuotes({ limit: 10 });
          setQuotes(quotesData);
          
          // Calculate stats
          const totalQuotes = quotesData.length;
          const acceptedQuotes = quotesData.filter(q => q.status === 'accepted').length;
          const successRate = totalQuotes > 0 ? Math.round((acceptedQuotes / totalQuotes) * 100) : 0;
          const totalRevenue = quotesData
            .filter(q => q.status === 'accepted')
            .reduce((sum, q) => sum + (q.total_amount || 0), 0);
          
          setStats({
            totalQuotes,
            thisMonth: totalQuotes, // Simplified for now
            successRate,
            totalRevenue
          });
        }
      } catch (err) {
        console.error('Failed to load dashboard data:', err);
        setError('Fehler beim Laden der Dashboard-Daten');
      } finally {
        setLoading(false);
      }
    };

    loadDashboardData();
  }, [demoMode]);

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

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('de-DE', {
      style: 'currency',
      currency: 'EUR'
    }).format(amount);
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('de-DE', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric'
    });
  };

  if (loading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
          {error}
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Dashboard</h1>
          <p className="text-gray-600">
            Willkommen zurück, {user?.company_name || user?.username || 'Demo User'}!
            {demoMode && <span className="ml-2 text-sm bg-blue-100 text-blue-800 px-2 py-1 rounded">Demo-Modus</span>}
          </p>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div className="bg-white rounded-lg shadow-md p-6 border-l-4 border-green-500">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">Neues Angebot</h3>
              <p className="text-gray-600 text-sm">Erstellen Sie ein neues Angebot mit unserem KI-Assistenten</p>
            </div>
            <div className="text-green-500 text-3xl">+</div>
          </div>
          <button
            onClick={() => onNavigate('new-quote')}
            className="mt-4 w-full bg-purple-600 text-white py-2 px-4 rounded-lg font-medium hover:bg-purple-700 transition-colors"
          >
            Neues Angebot
          </button>
        </div>

        <div className="bg-white rounded-lg shadow-md p-6 border-l-4 border-blue-500">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">Gesamt Angebote</h3>
              <p className="text-3xl font-bold text-blue-600">{stats.totalQuotes}</p>
            </div>
            <div className="text-blue-500 text-3xl">📄</div>
          </div>
          <p className="text-sm text-gray-600 mt-2">Diesen Monat</p>
        </div>

        <div className="bg-white rounded-lg shadow-md p-6 border-l-4 border-orange-500">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">Erfolgsquote</h3>
              <p className="text-3xl font-bold text-orange-600">{stats.successRate}%</p>
            </div>
            <div className="text-orange-500 text-3xl">📈</div>
          </div>
          <p className="text-sm text-gray-600 mt-2">Angenommene Angebote</p>
        </div>
      </div>

      {/* Recent Quotes */}
      <div className="bg-white rounded-lg shadow-md">
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-xl font-semibold text-gray-900">Letzte Angebote</h2>
        </div>
        
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Angebotsnummer
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Kunde
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Projekt
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Betrag
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Erstellt am
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {quotes.map((quote) => (
                <tr key={quote.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                    {quote.quote_number}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {quote.customer_name}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {quote.project_title}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {formatCurrency(quote.total_amount)}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${getStatusColor(quote.status)}`}>
                      {getStatusText(quote.status)}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {formatDate(quote.created_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {quotes.length === 0 && (
          <div className="px-6 py-8 text-center">
            <p className="text-gray-500">Noch keine Angebote erstellt.</p>
            <button
              onClick={() => onNavigate('new-quote')}
              className="mt-4 bg-blue-600 text-white py-2 px-4 rounded-lg font-medium hover:bg-blue-700 transition-colors"
            >
              Erstes Angebot erstellen
            </button>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-8">
        <Card className="p-6">
          <h3 className="text-lg font-semibold mb-4">Neuen Kostenvoranschlag erstellen</h3>
          <div className="space-y-4">
            <Button
              onClick={() => navigate('/create-quote')}
              className="w-full"
            >
              Klassischer Editor
            </Button>
            <Button
              onClick={() => navigate('/chat-quote')}
              className="w-full"
              variant="outline"
            >
              KI-Assistent
            </Button>
          </div>
        </Card>
      </div>
    </div>
  );
};

export default Dashboard;

