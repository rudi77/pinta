import React, { useEffect, useState } from 'react';
import { useAuth } from '../../hooks/useAuth';
import apiClient from '../../services/apiClient';
import CompanySection from './CompanySection';
import CostSection from './CostSection';
import LogoSection from './LogoSection';
import TelegramLinkCard from '../TelegramLinkCard';

const SettingsPage = () => {
  const { user, refreshUser, demoMode } = useAuth();
  const [profile, setProfile] = useState(user);
  const [loading, setLoading] = useState(!user);

  useEffect(() => {
    if (user) {
      setProfile(user);
      setLoading(false);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const fresh = await apiClient.getCurrentUser();
        if (!cancelled) setProfile(fresh);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [user]);

  const handleSaved = async () => {
    const fresh = await refreshUser();
    setProfile(fresh);
  };

  if (loading || !profile) {
    return (
      <div className="container mx-auto px-4 py-8">
        <p className="text-gray-500">Profil wird geladen…</p>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8 max-w-3xl">
      <h1 className="text-2xl font-bold text-gray-900 mb-2">Einstellungen</h1>
      <p className="text-sm text-gray-600 mb-8">
        Diese Werte landen automatisch in jedem neuen Angebot — Stundensatz,
        Materialaufschlag, Firmen-Header im PDF, Logo. Du kannst sie hier
        jederzeit aktualisieren.
      </p>

      <div className="space-y-6">
        <CompanySection profile={profile} onSaved={handleSaved} />
        <CostSection profile={profile} onSaved={handleSaved} />
        <LogoSection profile={profile} onSaved={handleSaved} />
        {!demoMode && <TelegramLinkCard />}
      </div>
    </div>
  );
};

export default SettingsPage;
