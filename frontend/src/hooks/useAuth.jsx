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
          setDemoMode(userData.email === 'demo@example.com');
        }
      } catch {
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
      setDemoMode(false);
      
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
  const demoLogin = async () => {
    setError(null);
    try {
      const response = await apiClient.demoLogin();
      localStorage.setItem('access_token', response.access_token);
      const userData = await apiClient.getCurrentUser();
      setIsAuthenticated(true);
      setDemoMode(true);
      setUser(userData);
      return response;
    } catch (err) {
      setError(err.message || 'Demo login failed');
      throw err;
    }
  };

  // Logout function
  const logout = async () => {
    try {
      if (!demoMode) {
        await apiClient.logout();
      }
    } catch (err) {
      setError(err.message || 'Logout failed');
    } finally {
      setIsAuthenticated(false);
      setUser(null);
      setDemoMode(false);
      apiClient.setToken(null);
    }
  };

  // Register function
  const register = async (userData) => {
    setError(null);
    try {
      const response = await apiClient.register(userData);
      // If the backend auto-verified the account (debug mode), log the user in.
      // Otherwise keep them logged out and let the UI show a "check your inbox" message.
      if (response && response.is_verified) {
        const loginResponse = await apiClient.login(userData.email, userData.password);
        localStorage.setItem('access_token', loginResponse.access_token);
        setIsAuthenticated(true);
        setDemoMode(false);
        const userDataFromApi = await apiClient.getCurrentUser();
        setUser(userDataFromApi);
      }
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

