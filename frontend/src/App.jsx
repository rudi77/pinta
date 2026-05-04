import React from 'react';
import { AuthProvider, useAuth } from './hooks/useAuth';
import Dashboard from './components/Dashboard';
import './App.css';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Login from './components/Login';
import Register from './components/Register';
import QuoteChat from './components/QuoteChat';
import QuoteDetail from './components/QuoteDetail';
import QuickQuote from './components/QuickQuote';
import PrivateRoute from './components/PrivateRoute';
import VerifyEmail from './components/VerifyEmail';
import OnboardingWizard from './components/Onboarding/OnboardingWizard';

// Header Component
const Header = () => {
  const { isAuthenticated, logout, user } = useAuth();

  return (
    <header className="bg-white shadow-sm border-b sticky top-0 z-10">
      <div className="container mx-auto px-4 py-4">
        <div className="flex justify-between items-center">
          <div className="flex items-center space-x-4">
            <h1 className="text-xl font-bold text-gray-900">Maler Kostenvoranschlag</h1>
            <span className="text-sm text-gray-500">Kostenvoranschläge per Chat</span>
          </div>
          
          <nav className="flex items-center space-x-4">
            {!isAuthenticated ? (
              <>
                <button 
                  onClick={() => window.location.href = '/login'}
                  className="bg-blue-600 text-white px-4 py-2 rounded-lg font-medium hover:bg-blue-700 transition-colors"
                >
                  Anmelden
                </button>
                <button 
                  onClick={() => window.location.href = '/register'}
                  className="bg-green-600 text-white px-4 py-2 rounded-lg font-medium hover:bg-green-700 transition-colors"
                >
                  Registrieren
                </button>
              </>
            ) : (
              <>
                <button
                  onClick={() => window.location.href = '/dashboard'}
                  className="text-gray-600 hover:text-gray-900 px-3 py-2 rounded-md text-sm font-medium"
                >
                  Dashboard
                </button>
                <button
                  onClick={() => window.location.href = '/quote/new'}
                  className="bg-blue-600 text-white px-3 py-2 rounded-md text-sm font-medium hover:bg-blue-700 transition-colors"
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

// Main App Component
function App() {
  return (
    <Router>
      <AuthProvider>
        <div className="min-h-screen bg-gray-50">
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            <Route path="/verify-email" element={<VerifyEmail />} />
            <Route
              path="/onboarding"
              element={
                <PrivateRoute allowWithoutOnboarding>
                  <OnboardingWizard />
                </PrivateRoute>
              }
            />
            <Route path="/quick-quote" element={<PrivateRoute><QuickQuote /></PrivateRoute>} />
            <Route path="/dashboard" element={<PrivateRoute><Dashboard /></PrivateRoute>} />
            <Route path="/quote/new" element={<PrivateRoute><QuoteChat /></PrivateRoute>} />
            <Route path="/chat-quote" element={<Navigate to="/quote/new" replace />} />
            <Route path="/new-quote" element={<Navigate to="/quote/new" replace />} />
            <Route path="/quotes/:quoteId" element={<PrivateRoute><QuoteDetail /></PrivateRoute>} />
            <Route path="/" element={<Navigate to="/dashboard" />} />
          </Routes>
        </div>
      </AuthProvider>
    </Router>
  );
}

export default App;

