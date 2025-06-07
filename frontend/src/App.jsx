import React from 'react';
import { AuthProvider, useAuth } from './hooks/useAuth';
import Dashboard from './components/Dashboard';
import QuoteCreator from './components/QuoteCreator';
import apiClient from './services/apiClient';
import './App.css';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Login from './components/Login';
import Register from './components/Register';
import ChatQuoteWizard from './components/ChatQuoteWizard';

// Header Component
const Header = () => {
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
                  onClick={() => window.location.href = '/new-quote'}
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

// Main App Component
function App() {
  return (
    <Router>
      <AuthProvider>
        <div className="min-h-screen bg-gray-50">
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/new-quote" element={<QuoteCreator />} />
            <Route path="/chat-quote" element={<ChatQuoteWizard />} />
            <Route path="/" element={<Navigate to="/login" />} />
          </Routes>
        </div>
      </AuthProvider>
    </Router>
  );
}

export default App;

