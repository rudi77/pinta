import React, { createContext, useContext, useState, useEffect } from 'react';
import apiClient from '../services/apiClient';

// Create auth context
const AuthContext = createContext();

// Auth provider component
export function AuthProvider({ children }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [demoMode, setDemoMode] = useState(false);

  // Check if user is authenticated on mount
  useEffect(() => {
    const checkAuth = async () => {
      try {
        // Check if token exists
        const token = localStorage.getItem('access_token');
        
        if (token) {
          // Validate token by fetching user data
          const userData = await apiClient.getCurrentUser();
          setUser(userData);
          setIsAuthenticated(true);
        }
      } catch (err) {
        console.error('Authentication check failed:', err);
        // Clear invalid token
        localStorage.removeItem('access_token');
        setIsAuthenticated(false);
        setUser(null);
      } finally {
        setLoading(false);
      }
    };

    checkAuth();

    // Listen for auth:logout event
    const handleLogout = () => {
      setIsAuthenticated(false);
      setUser(null);
      setDemoMode(false);
    };

    window.addEventListener('auth:logout', handleLogout);
    return () => window.removeEventListener('auth:logout', handleLogout);
  }, []);

  // Login function
  const login = async (email, password) => {
    setError(null);
    try {
      const response = await apiClient.login(email, password);
      localStorage.setItem('access_token', response.access_token);
      setIsAuthenticated(true);
      
      // Fetch user data
      const userData = await apiClient.getCurrentUser();
      setUser(userData);
      
      return response;
    } catch (err) {
      setError(err.message || 'Login failed');
      throw err;
    }
  };

  // Demo login function
  const demoLogin = () => {
    setIsAuthenticated(true);
    setDemoMode(true);
    setUser({
      id: 'demo-user',
      username: 'demo',
      email: 'demo@example.com',
      company_name: 'Demo Malerbetrieb',
      is_premium: true
    });
  };

  // Logout function
  const logout = async () => {
    try {
      if (!demoMode) {
        await apiClient.logout();
      }
    } catch (err) {
      console.error('Logout error:', err);
    } finally {
      setIsAuthenticated(false);
      setUser(null);
      setDemoMode(false);
    }
  };

  // Register function
  const register = async (userData) => {
    setError(null);
    try {
      const response = await apiClient.register(userData);
      // After successful registration, log the user in
      const loginResponse = await apiClient.login(userData.email, userData.password);
      localStorage.setItem('access_token', loginResponse.access_token);
      setIsAuthenticated(true);
      
      // Fetch user data
      const userData = await apiClient.getCurrentUser();
      setUser(userData);
      
      return response;
    } catch (err) {
      setError(err.message || 'Registration failed');
      throw err;
    }
  };

  // Context value
  const value = {
    isAuthenticated,
    user,
    loading,
    error,
    demoMode,
    login,
    demoLogin,
    logout,
    register
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// Custom hook to use auth context
export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

export default useAuth;

