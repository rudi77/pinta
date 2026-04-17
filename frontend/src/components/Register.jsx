import React, { useState, useEffect } from 'react';
import { useAuth } from '../hooks/useAuth';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Card } from './ui/card';
import { useNavigate } from 'react-router-dom';

const Register = () => {
  const { register, error, isAuthenticated } = useAuth();
  const [email, setEmail] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [verificationPending, setVerificationPending] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    if (isAuthenticated) {
      navigate('/quick-quote');
    }
  }, [isAuthenticated, navigate]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (password !== confirmPassword) {
      alert('Passwörter stimmen nicht überein');
      return;
    }
    try {
      const response = await register({ email, username, password });
      if (response && response.is_verified === false) {
        setVerificationPending(true);
      }
    } catch (error) {
      // Error is already handled by useAuth
    }
  };

  if (verificationPending) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
        <Card className="max-w-md w-full space-y-6 p-8 text-center">
          <h2 className="text-2xl font-bold text-gray-900">Fast geschafft!</h2>
          <p className="text-gray-600">
            Wir haben dir einen Bestätigungslink an <strong>{email}</strong> geschickt.
            Bitte öffne die E-Mail und klicke auf den Link, um dein Konto zu aktivieren.
          </p>
          <Button className="w-full" onClick={() => navigate('/login')}>
            Zum Login
          </Button>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <Card className="max-w-md w-full space-y-8 p-8">
        <div>
          <h2 className="mt-6 text-center text-3xl font-extrabold text-gray-900">
            Registrieren
          </h2>
        </div>
        <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
          <div className="rounded-md shadow-sm -space-y-px">
            <div>
              <Input
                type="text"
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Benutzername"
                autoComplete="username"
                className="mb-4"
              />
            </div>
            <div>
              <Input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="E-Mail-Adresse"
                autoComplete="email"
                className="mb-4"
              />
            </div>
            <div>
              <Input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Passwort"
                autoComplete="new-password"
                className="mb-4"
              />
            </div>
            <div>
              <Input
                type="password"
                required
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Passwort bestätigen"
                autoComplete="new-password"
              />
            </div>
          </div>

          {error && (
            <div className="text-red-500 text-sm text-center">{error}</div>
          )}

          <div className="space-y-4">
            <Button type="submit" className="w-full">
              Registrieren
            </Button>
            <Button
              type="button"
              variant="link"
              onClick={() => navigate('/login')}
              className="w-full"
            >
              Bereits ein Konto? Anmelden
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
};

export default Register; 