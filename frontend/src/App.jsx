import React, { useState } from 'react';
import { AuthProvider, useAuth } from './hooks/useAuth';
import Dashboard from './components/Dashboard';
import QuoteCreator from './components/QuoteCreator';
import apiClient from './services/apiClient';
import './App.css';

// Header Component
const Header = ({ onNavigate }) => {
  const { isAuthenticated, logout, user } = useAuth();

  return (
    <header className="bg-white shadow-sm border-b sticky top-0 z-10">
      <div className="container mx-auto px-4 py-4">
        <div className="flex justify-between items-center">
          <div className="flex items-center space-x-4">
            <h1 className="text-xl font-bold text-gray-900">Maler Kostenvoranschlag</h1>
            <span className="text-sm text-gray-500">KI-gestützter Kostenvoranschlags-Generator</span>
          </div>
          
          <nav className="flex items-center space-x-4">
            {!isAuthenticated ? (
              <>
                <button 
                  onClick={() => onNavigate('landing')}
                  className="text-gray-600 hover:text-gray-900 px-3 py-2 rounded-md text-sm font-medium"
                >
                  Features
                </button>
                <button 
                  onClick={() => onNavigate('landing')}
                  className="text-gray-600 hover:text-gray-900 px-3 py-2 rounded-md text-sm font-medium"
                >
                  Preise
                </button>
                <button 
                  onClick={() => onNavigate('landing')}
                  className="text-gray-600 hover:text-gray-900 px-3 py-2 rounded-md text-sm font-medium"
                >
                  Kontakt
                </button>
                <button 
                  onClick={() => onNavigate('login')}
                  className="bg-blue-600 text-white px-4 py-2 rounded-lg font-medium hover:bg-blue-700 transition-colors"
                >
                  Anmelden
                </button>
                <button 
                  onClick={() => onNavigate('login')}
                  className="bg-green-600 text-white px-4 py-2 rounded-lg font-medium hover:bg-green-700 transition-colors"
                >
                  Registrieren
                </button>
              </>
            ) : (
              <>
                <button 
                  onClick={() => onNavigate('dashboard')}
                  className="text-gray-600 hover:text-gray-900 px-3 py-2 rounded-md text-sm font-medium"
                >
                  Dashboard
                </button>
                <button 
                  onClick={() => onNavigate('new-quote')}
                  className="text-gray-600 hover:text-gray-900 px-3 py-2 rounded-md text-sm font-medium"
                >
                  Neues Angebot
                </button>
                <span className="text-sm text-gray-600">
                  Hallo, {user?.username || user?.company_name || 'User'}
                </span>
                <button 
                  onClick={logout}
                  className="bg-red-600 text-white px-4 py-2 rounded-lg font-medium hover:bg-red-700 transition-colors"
                >
                  Abmelden
                </button>
              </>
            )}
          </nav>
        </div>
      </div>
    </header>
  );
};

// Landing Page Component
const LandingPage = ({ onNavigate }) => (
  <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
    <Header onNavigate={onNavigate} />
    
    <main className="container mx-auto px-4 py-16">
      <div className="text-center mb-16">
        <h1 className="text-5xl font-bold text-gray-900 mb-6">
          KI-gestützter Kostenvoranschlag für Malerbetriebe
        </h1>
        <p className="text-xl text-gray-600 mb-8 max-w-3xl mx-auto">
          Erstellen Sie professionelle Kostenvoranschläge in wenigen Minuten. Unsere KI analysiert Ihre Eingaben und Pläne automatisch und erstellt detaillierte Angebote.
        </p>
        
        <div className="flex justify-center space-x-4">
          <button
            onClick={() => onNavigate('login')}
            className="bg-purple-600 text-white px-8 py-3 rounded-lg text-lg font-medium hover:bg-purple-700 transition-colors"
          >
            Kostenlos testen
          </button>
          <button
            onClick={() => onNavigate('login')}
            className="bg-white text-purple-600 border-2 border-purple-600 px-8 py-3 rounded-lg text-lg font-medium hover:bg-purple-50 transition-colors"
          >
            Demo ansehen
          </button>
        </div>
      </div>

      <div className="grid md:grid-cols-3 gap-8 mb-16">
        <div className="bg-white p-8 rounded-lg shadow-lg hover:shadow-xl transition-shadow">
          <div className="text-4xl mb-4">🤖</div>
          <h3 className="text-xl font-semibold mb-4">KI-gestützt</h3>
          <p className="text-gray-600">
            Intelligente Analyse Ihrer Eingaben und automatische Generierung von Angebotsposition
          </p>
        </div>

        <div className="bg-white p-8 rounded-lg shadow-lg hover:shadow-xl transition-shadow">
          <div className="text-4xl mb-4">📋</div>
          <h3 className="text-xl font-semibold mb-4">Planauswertung</h3>
          <p className="text-gray-600">
            Automatische Erkennung von Räumen, Flächen und Materialien aus hochgeladenen Bauplänen
          </p>
        </div>

        <div className="bg-white p-8 rounded-lg shadow-lg hover:shadow-xl transition-shadow">
          <div className="text-4xl mb-4">⚡</div>
          <h3 className="text-xl font-semibold mb-4">Schnell & Einfach</h3>
          <p className="text-gray-600">
            Von der Eingabe zum fertigen PDF-Angebot in unter 5 Minuten - keine komplizierte Software nötig
          </p>
        </div>
      </div>
    </main>
  </div>
);

// Login Component
const Login = ({ onNavigate }) => {
  const { login, demoLogin, error } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await login(email, password);
      onNavigate('dashboard');
    } catch (err) {
      console.error('Login failed:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleDemoLogin = () => {
    demoLogin();
    onNavigate('dashboard');
  };

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="max-w-md w-full bg-white rounded-lg shadow-lg p-8">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold text-gray-900 mb-2">Maler Kostenvoranschlag</h1>
          <p className="text-gray-600">KI-gestützter Kostenvoranschlags-Generator</p>
        </div>

        <h2 className="text-xl font-semibold mb-6">Willkommen</h2>
        <p className="text-gray-600 mb-6">Melden Sie sich an oder erstellen Sie ein neues Konto</p>

        <div className="flex space-x-2 mb-6">
          <button className="flex-1 bg-green-600 text-white py-2 px-4 rounded-lg font-medium hover:bg-green-700 transition-colors">
            Anmelden
          </button>
          <button className="flex-1 bg-blue-600 text-white py-2 px-4 rounded-lg font-medium hover:bg-blue-700 transition-colors">
            Registrieren
          </button>
        </div>

        <form onSubmit={handleLogin} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">E-Mail *</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="ihre@email.de"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Passwort *</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="••••••••"
              required
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 text-white py-2 px-4 rounded-lg font-medium hover:bg-blue-700 transition-colors disabled:opacity-50"
          >
            {loading ? 'Anmelden...' : 'Anmelden'}
          </button>
        </form>

        {error && (
          <div className="mt-4 p-3 bg-red-100 border border-red-400 text-red-700 rounded">
            {error}
          </div>
        )}

        <div className="mt-6 text-center">
          <p className="text-gray-600 mb-4">ODER</p>
          <button
            onClick={handleDemoLogin}
            className="w-full bg-green-600 text-white py-2 px-4 rounded-lg font-medium hover:bg-green-700 transition-colors"
          >
            Demo-Modus testen
          </button>
        </div>

        <div className="mt-6 text-center">
          <p className="text-sm text-gray-600">
            Mit der Nutzung stimmen Sie unseren{' '}
            <button className="text-blue-600 hover:underline">Nutzungsbedingungen</button> zu.
          </p>
        </div>
      </div>
    </div>
  );
};

// Main App Component
function App() {
  const [currentView, setCurrentView] = useState('landing');

  // Landing Page Component
  const LandingPageWrapper = () => (
    <LandingPage onNavigate={setCurrentView} />
  );

  // Protected Route Component
  const ProtectedRoute = ({ children }) => {
    const { isAuthenticated } = useAuth();
    
    if (!isAuthenticated) {
      return <Login onNavigate={setCurrentView} />;
    }
    
    return children;
  };

  // Main App Router
  const renderCurrentView = () => {
    switch (currentView) {
      case 'landing':
        return <LandingPageWrapper />;
      case 'login':
        return <Login onNavigate={setCurrentView} />;
      case 'dashboard':
        return (
          <ProtectedRoute>
            <div className="min-h-screen bg-gray-50">
              <Header onNavigate={setCurrentView} />
              <Dashboard onNavigate={setCurrentView} />
            </div>
          </ProtectedRoute>
        );
      case 'new-quote':
        return (
          <ProtectedRoute>
            <div className="min-h-screen bg-gray-50">
              <Header onNavigate={setCurrentView} />
              <QuoteCreator onNavigate={setCurrentView} />
            </div>
          </ProtectedRoute>
        );
      default:
        return <LandingPageWrapper />;
    }
  };

  return (
    <AuthProvider>
      <div className="App">
        {renderCurrentView()}
      </div>
    </AuthProvider>
  );
}

export default App;

