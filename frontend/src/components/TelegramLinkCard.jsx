import React, { useEffect, useState } from 'react';
import { Card } from './ui/card';
import { Button } from './ui/button';
import apiClient from '../services/apiClient';

const formatLastSeen = (iso) => {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('de-DE', {
      day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  } catch {
    return iso;
  }
};

const TelegramLinkCard = () => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [status, setStatus] = useState({ links: [], bot_username: null });
  const [token, setToken] = useState(null);
  const [tokenExpires, setTokenExpires] = useState(null);
  const [deepLink, setDeepLink] = useState(null);
  const [copied, setCopied] = useState(false);
  const [generating, setGenerating] = useState(false);

  const refresh = async () => {
    try {
      const data = await apiClient.getChannelLinks();
      setStatus(data);
      setError(null);
    } catch (err) {
      setError(err.message || 'Status konnte nicht geladen werden');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { refresh(); }, []);

  const telegramLinks = (status.links || []).filter(
    (l) => l.channel === 'telegram' && !l.is_anonymous_shadow,
  );
  const isLinked = telegramLinks.length > 0;

  const handleGenerate = async () => {
    setGenerating(true);
    setError(null);
    try {
      const data = await apiClient.createTelegramLinkingToken();
      setToken(data.token);
      setTokenExpires(data.expires_at);
      setDeepLink(data.deep_link || null);
    } catch (err) {
      setError(err.message || 'Token konnte nicht erzeugt werden');
    } finally {
      setGenerating(false);
    }
  };

  const handleCopy = async (text) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  };

  if (loading) {
    return (
      <Card className="p-6">
        <h3 className="text-lg font-semibold">Telegram</h3>
        <p className="text-sm text-gray-500 mt-2">Status wird geladen…</p>
      </Card>
    );
  }

  return (
    <Card className="p-6">
      <h3 className="text-lg font-semibold">Telegram-Bot</h3>

      {isLinked && !token && (
        <>
          <p className="text-sm text-green-700 mt-2">
            ✅ Verbunden mit Telegram. Angebote aus dem Bot-Chat landen
            jetzt hier im Dashboard.
          </p>
          <ul className="mt-3 space-y-1 text-sm text-gray-600">
            {telegramLinks.map((l) => (
              <li key={l.id}>
                Chat <code className="bg-gray-100 px-1 rounded">{l.external_id}</code>
                {l.display_name ? ` — ${l.display_name}` : ''}
                <span className="text-gray-400"> · zuletzt {formatLastSeen(l.last_seen_at)}</span>
              </li>
            ))}
          </ul>
          <div className="mt-4">
            <Button
              variant="outline"
              size="sm"
              onClick={handleGenerate}
              disabled={generating}
            >
              {generating ? 'Erzeuge…' : 'Weiteren Chat verbinden'}
            </Button>
          </div>
        </>
      )}

      {!isLinked && !token && (
        <>
          <p className="text-sm text-gray-600 mt-2">
            Verknüpfe deinen Telegram-Chat mit deinem Pinta-Account, damit
            Angebote, die du dem Bot diktierst, hier im Dashboard auftauchen.
          </p>
          <div className="mt-4">
            <Button onClick={handleGenerate} disabled={generating}>
              {generating ? 'Erzeuge…' : 'Telegram verbinden'}
            </Button>
          </div>
        </>
      )}

      {token && (
        <div className="mt-4 space-y-3">
          <p className="text-sm text-gray-700">
            Dein Verbindungs-Code (gültig bis{' '}
            <strong>{formatLastSeen(tokenExpires)}</strong>):
          </p>

          {deepLink ? (
            <div className="rounded-md border border-blue-200 bg-blue-50 p-3 space-y-2">
              <p className="text-sm">
                <strong>Empfohlen:</strong> auf den Link klicken — Telegram
                öffnet automatisch und der Bot ist sofort verbunden.
              </p>
              <a
                href={deepLink}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center text-sm font-medium text-blue-700 underline break-all"
              >
                {deepLink}
              </a>
            </div>
          ) : (
            <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm">
              <p>
                Kein Bot-Username konfiguriert (
                <code>TELEGRAM_BOT_USERNAME</code> in <code>.env</code>) — nutze
                stattdessen den manuellen Befehl unten.
              </p>
            </div>
          )}

          <div className="rounded-md border border-gray-200 bg-gray-50 p-3 space-y-2">
            <p className="text-sm">Oder im Telegram-Chat tippen:</p>
            <div className="flex items-center gap-2">
              <code className="flex-1 break-all rounded bg-white border border-gray-300 px-2 py-1 text-sm font-mono">
                /link {token}
              </code>
              <Button
                size="sm"
                variant="outline"
                onClick={() => handleCopy(`/link ${token}`)}
              >
                {copied ? 'Kopiert' : 'Kopieren'}
              </Button>
            </div>
          </div>

          <Button variant="outline" size="sm" onClick={refresh}>
            Status erneut prüfen
          </Button>
        </div>
      )}

      {error && (
        <p className="mt-3 text-sm text-red-600" role="alert">
          {error}
        </p>
      )}
    </Card>
  );
};

export default TelegramLinkCard;
