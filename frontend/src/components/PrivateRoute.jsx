import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

const PrivateRoute = ({ children, allowWithoutOnboarding = false }) => {
  const { isAuthenticated, loading, onboardingComplete } = useAuth();
  const location = useLocation();

  if (loading) {
    return <div>Lade Authentifizierung...</div>;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" />;
  }

  if (
    !onboardingComplete &&
    !allowWithoutOnboarding &&
    location.pathname !== '/onboarding'
  ) {
    return <Navigate to="/onboarding" replace />;
  }

  return children;
};

export default PrivateRoute;
