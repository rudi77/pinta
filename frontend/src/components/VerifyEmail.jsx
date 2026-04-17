import React, { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import apiClient from '../services/apiClient';
import { Button } from './ui/button';
import { Card } from './ui/card';

const STATUS = {
  PENDING: 'pending',
  SUCCESS: 'success',
  ERROR: 'error',
};

const VerifyEmail = () => {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const token = params.get('token');
  const [status, setStatus] = useState(STATUS.PENDING);
  const [message, setMessage] = useState('E-Mail-Adresse wird verifiziert...');

  useEffect(() => {
    if (!token) {
      setStatus(STATUS.ERROR);
      setMessage('Kein Verifizierungs-Token in der URL gefunden.');
      return;
    }

    let cancelled = false;
    (async () => {
      try {
        await apiClient.verifyEmail(token);
        if (cancelled) return;
        setStatus(STATUS.SUCCESS);
        setMessage('Deine E-Mail-Adresse wurde erfolgreich verifiziert. Du kannst dich jetzt anmelden.');
      } catch (err) {
        if (cancelled) return;
        setStatus(STATUS.ERROR);
        setMessage(err.message || 'Verifizierung fehlgeschlagen. Der Link ist möglicherweise abgelaufen.');
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [token]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <Card className="max-w-md w-full space-y-6 p-8 text-center">
        <h2 className="text-2xl font-bold text-gray-900">E-Mail-Verifizierung</h2>
        <p
          className={
            status === STATUS.SUCCESS
              ? 'text-green-600'
              : status === STATUS.ERROR
              ? 'text-red-600'
              : 'text-gray-600'
          }
        >
          {message}
        </p>
        {status !== STATUS.PENDING && (
          <div className="space-y-3">
            <Button className="w-full" onClick={() => navigate('/login')}>
              Zum Login
            </Button>
            {status === STATUS.ERROR && (
              <Button
                variant="outline"
                className="w-full"
                onClick={() => navigate('/register')}
              >
                Neu registrieren
              </Button>
            )}
          </div>
        )}
      </Card>
    </div>
  );
};

export default VerifyEmail;
