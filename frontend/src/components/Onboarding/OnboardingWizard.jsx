import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card } from '../ui/card';
import { Button } from '../ui/button';
import { useAuth } from '../../hooks/useAuth';
import apiClient from '../../services/apiClient';
import Step1Company from './Step1Company';
import Step2CostParams from './Step2CostParams';
import Step3Logo from './Step3Logo';

const TOTAL_STEPS = 3;

const ProgressBar = ({ step }) => (
  <div className="flex items-center gap-2 mb-6">
    {[1, 2, 3].map((n) => (
      <div
        key={n}
        className={`flex-1 h-1.5 rounded-full ${
          n <= step ? 'bg-blue-600' : 'bg-gray-200'
        }`}
      />
    ))}
    <span className="text-xs text-gray-500 w-12 text-right">
      Schritt {step}/{TOTAL_STEPS}
    </span>
  </div>
);

const OnboardingWizard = () => {
  const navigate = useNavigate();
  const { refreshUser } = useAuth();

  const [step, setStep] = useState(1);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const [companyData, setCompanyData] = useState({
    company_name: '',
    address: '',
    vat_id: '',
  });
  const [costData, setCostData] = useState({
    hourly_rate: 45,
    material_cost_markup: 15,
  });
  const [logoFile, setLogoFile] = useState(null);

  const goNext = () => setStep((s) => Math.min(TOTAL_STEPS, s + 1));
  const goBack = () => setStep((s) => Math.max(1, s - 1));

  const handleFinish = async () => {
    setSubmitting(true);
    setError(null);
    try {
      if (logoFile) {
        await apiClient.uploadLogo(logoFile);
      }
      await apiClient.completeOnboarding({
        company_name: companyData.company_name,
        address: companyData.address,
        vat_id: companyData.vat_id || null,
        hourly_rate: Number(costData.hourly_rate),
        material_cost_markup: Number(costData.material_cost_markup),
      });
      // Backend has already flipped onboarding_completed_at; if the
      // refresh fails (transient network), we still want to land on the
      // dashboard rather than trapping the user on this screen.
      try {
        await refreshUser();
      } catch (refreshErr) {
        console.warn('refreshUser failed after onboarding', refreshErr);
      }
      navigate('/dashboard');
    } catch (err) {
      setError(err.message || 'Onboarding konnte nicht abgeschlossen werden');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4">
      <Card className="max-w-2xl w-full p-8">
        <div className="mb-4">
          <h1 className="text-2xl font-bold text-gray-900">Willkommen!</h1>
          <p className="text-sm text-gray-600">
            Drei kurze Schritte und du kannst Angebote erstellen.
          </p>
        </div>
        <ProgressBar step={step} />

        {step === 1 && (
          <Step1Company
            value={companyData}
            onChange={setCompanyData}
            onNext={goNext}
          />
        )}
        {step === 2 && (
          <Step2CostParams
            value={costData}
            onChange={setCostData}
            onBack={goBack}
            onNext={goNext}
          />
        )}
        {step === 3 && (
          <Step3Logo
            file={logoFile}
            onChange={setLogoFile}
            onBack={goBack}
            onFinish={handleFinish}
            submitting={submitting}
          />
        )}

        {error && (
          <div className="mt-4 text-red-600 text-sm" role="alert">
            {error}
          </div>
        )}
      </Card>
    </div>
  );
};

export default OnboardingWizard;
