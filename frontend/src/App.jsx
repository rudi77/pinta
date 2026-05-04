import React from 'react';
import { AuthProvider } from './hooks/useAuth';
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
import SettingsPage from './components/Settings/SettingsPage';
import AppLayout from './components/layout/AppLayout';

// Convenience wrapper: gate by auth + onboarding AND wrap with the
// sidebar-shell. Login/register/onboarding/verify-email stay full-screen
// (they need to work before the sidebar is meaningful).
const ShellRoute = ({ children }) => (
  <PrivateRoute>
    <AppLayout>{children}</AppLayout>
  </PrivateRoute>
);

function App() {
  return (
    <Router>
      <AuthProvider>
        <Routes>
          {/* Full-screen pages — no sidebar */}
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

          {/* App pages — sidebar shell */}
          <Route path="/quick-quote" element={<ShellRoute><QuickQuote /></ShellRoute>} />
          <Route path="/dashboard" element={<ShellRoute><Dashboard /></ShellRoute>} />
          <Route path="/quote/new" element={<ShellRoute><QuoteChat /></ShellRoute>} />
          <Route path="/chat-quote" element={<Navigate to="/quote/new" replace />} />
          <Route path="/new-quote" element={<Navigate to="/quote/new" replace />} />
          <Route path="/quotes/:quoteId" element={<ShellRoute><QuoteDetail /></ShellRoute>} />
          <Route path="/settings" element={<ShellRoute><SettingsPage /></ShellRoute>} />
          <Route path="/" element={<Navigate to="/dashboard" />} />
        </Routes>
      </AuthProvider>
    </Router>
  );
}

export default App;
