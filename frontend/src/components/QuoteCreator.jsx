import React, { useState } from 'react';
import { useAuth } from '../hooks/useAuth';
import apiClient from '../services/apiClient';

const QuoteCreator = ({ onNavigate }) => {
  const { user, demoMode } = useAuth();
  const [currentStep, setCurrentStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  
  // Form data
  const [formData, setFormData] = useState({
    // Project data
    project_title: '',
    project_description: '',
    rooms: 1,
    area_sqm: '',
    
    // Customer data
    customer_name: '',
    customer_email: '',
    customer_phone: '',
    customer_address: '',
    
    // Files
    files: []
  });
  
  const updateFormData = (field, value) => {
    setFormData(prev => ({
      ...prev,
      [field]: value
    }));
  };
  
  const handleNextStep = () => {
    setCurrentStep(prev => prev + 1);
  };
  
  const handlePrevStep = () => {
    setCurrentStep(prev => prev - 1);
  };
  
  const handleFileUpload = (e) => {
    const files = Array.from(e.target.files);
    setFormData(prev => ({
      ...prev,
      files: [...prev.files, ...files]
    }));
  };
  
  const removeFile = (index) => {
    setFormData(prev => ({
      ...prev,
      files: prev.files.filter((_, i) => i !== index)
    }));
  };
  
  const handleSubmit = async () => {
    setLoading(true);
    setError(null);
    
    try {
      if (demoMode) {
        // Simulate API call in demo mode
        await new Promise(resolve => setTimeout(resolve, 2000));
        onNavigate('dashboard');
        return;
      }
      
      // Create quote via API
      const quoteData = {
        customer_name: formData.customer_name,
        customer_email: formData.customer_email,
        customer_phone: formData.customer_phone,
        customer_address: formData.customer_address,
        project_title: formData.project_title,
        project_description: formData.project_description,
        quote_items: [] // Will be filled by AI
      };
      
      const newQuote = await apiClient.createQuote(quoteData);
      
      // Generate quote items with AI
      await apiClient.generateQuoteWithAI(
        newQuote.id, 
        formData.project_description
      );
      
      // Upload files if any
      if (formData.files.length > 0) {
        // File upload logic would go here
        // This would typically involve a separate API endpoint
      }
      
      // Navigate back to dashboard
      onNavigate('dashboard');
      
    } catch (err) {
      console.error('Failed to create quote:', err);
      setError('Fehler beim Erstellen des Angebots: ' + (err.message || 'Unbekannter Fehler'));
    } finally {
      setLoading(false);
    }
  };
  
  // Validate current step
  const validateStep = () => {
    switch (currentStep) {
      case 1: // Project data
        return formData.project_title && formData.project_description;
      case 2: // Customer data
        return formData.customer_name;
      case 3: // Files (optional)
        return true;
      default:
        return true;
    }
  };
  
  // Render step content
  const renderStepContent = () => {
    switch (currentStep) {
      case 1:
        return (
          <div className="space-y-6">
            <h2 className="text-xl font-semibold">Projektdaten</h2>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Projektname *</label>
              <input
                type="text"
                value={formData.project_title}
                onChange={(e) => updateFormData('project_title', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="z.B. Renovierung Wohnzimmer"
                required
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Projektbeschreibung *</label>
              <textarea
                value={formData.project_description}
                onChange={(e) => updateFormData('project_description', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                rows={5}
                placeholder="Beschreiben Sie das Projekt detailliert (z.B. Raumgröße, Farbe, besondere Anforderungen)"
                required
              />
            </div>
            
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Anzahl der Räume</label>
                <input
                  type="number"
                  value={formData.rooms}
                  onChange={(e) => updateFormData('rooms', parseInt(e.target.value) || 1)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  min={1}
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Gesamtfläche (m²)</label>
                <input
                  type="number"
                  value={formData.area_sqm}
                  onChange={(e) => updateFormData('area_sqm', e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  placeholder="z.B. 25"
                />
              </div>
            </div>
          </div>
        );
        
      case 2:
        return (
          <div className="space-y-6">
            <h2 className="text-xl font-semibold">Kundendaten</h2>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Kundenname *</label>
              <input
                type="text"
                value={formData.customer_name}
                onChange={(e) => updateFormData('customer_name', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="Vor- und Nachname"
                required
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">E-Mail</label>
              <input
                type="email"
                value={formData.customer_email}
                onChange={(e) => updateFormData('customer_email', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="kunde@beispiel.de"
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Telefon</label>
              <input
                type="tel"
                value={formData.customer_phone}
                onChange={(e) => updateFormData('customer_phone', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="+49 123 4567890"
              />
            </div>
          </div>
        );
        
      case 3:
        return (
          <div className="space-y-6">
            <h2 className="text-xl font-semibold">Dokumente hochladen</h2>
            <p className="text-gray-600">Laden Sie Baupläne, Fotos oder andere relevante Dokumente hoch (optional)</p>
            
            <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center">
              <div className="flex flex-col items-center">
                <div className="text-yellow-500 text-4xl mb-2">📁</div>
                <label className="cursor-pointer">
                  <span className="text-blue-600 hover:underline">Dateien auswählen</span>
                  <input
                    type="file"
                    multiple
                    onChange={handleFileUpload}
                    className="hidden"
                    accept="image/*, application/pdf, .doc, .docx"
                  />
                </label>
                <span className="text-gray-500 text-sm mt-1">oder per Drag & Drop</span>
                <span className="text-gray-400 text-xs mt-1">PDF, JPG, PNG, DOC, DOCX</span>
              </div>
            </div>
            
            {formData.files.length > 0 && (
              <div className="mt-4">
                <h3 className="text-sm font-medium text-gray-700 mb-2">Hochgeladene Dateien:</h3>
                <ul className="space-y-2">
                  {formData.files.map((file, index) => (
                    <li key={index} className="flex items-center justify-between bg-gray-50 p-2 rounded">
                      <span className="text-sm text-gray-800">{file.name}</span>
                      <button
                        onClick={() => removeFile(index)}
                        className="text-red-500 hover:text-red-700"
                      >
                        ✕
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        );
        
      case 4:
        return (
          <div className="space-y-6">
            <h2 className="text-xl font-semibold">Angebot erstellen</h2>
            
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
              <h3 className="text-lg font-medium text-gray-900 mb-4">📋 Zusammenfassung</h3>
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-sm font-medium text-gray-700">Projektname:</p>
                  <p className="text-sm text-gray-900">{formData.project_title}</p>
                </div>
                
                <div>
                  <p className="text-sm font-medium text-gray-700">Kunde:</p>
                  <p className="text-sm text-gray-900">{formData.customer_name}</p>
                </div>
                
                <div>
                  <p className="text-sm font-medium text-gray-700">Räume:</p>
                  <p className="text-sm text-gray-900">{formData.rooms}</p>
                </div>
                
                <div>
                  <p className="text-sm font-medium text-gray-700">Fläche:</p>
                  <p className="text-sm text-gray-900">{formData.area_sqm} m²</p>
                </div>
              </div>
              
              <div className="mt-4">
                <p className="text-sm font-medium text-gray-700">Beschreibung:</p>
                <p className="text-sm text-gray-900">{formData.project_description}</p>
              </div>
              
              <div className="mt-4">
                <p className="text-sm font-medium text-gray-700">Dateien:</p>
                <p className="text-sm text-gray-900">
                  {formData.files.length} Dokument(e)
                </p>
              </div>
            </div>
            
            <div className="bg-green-50 border border-green-200 rounded-lg p-6">
              <h3 className="text-lg font-medium text-gray-900 mb-4">🤖 KI-Analyse</h3>
              <p className="text-sm text-gray-700 mb-4">
                Unsere KI wird Ihre Eingaben analysieren und automatisch:
              </p>
              
              <ul className="space-y-2 text-sm text-gray-700">
                <li className="flex items-center">
                  <span className="text-green-500 mr-2">✓</span>
                  Materialkosten berechnen
                </li>
                <li className="flex items-center">
                  <span className="text-green-500 mr-2">✓</span>
                  Arbeitszeit schätzen
                </li>
                <li className="flex items-center">
                  <span className="text-green-500 mr-2">✓</span>
                  Professionelles PDF erstellen
                </li>
                <li className="flex items-center">
                  <span className="text-green-500 mr-2">✓</span>
                  Preisvorschläge generieren
                </li>
              </ul>
            </div>
            
            {error && (
              <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
                {error}
              </div>
            )}
          </div>
        );
        
      default:
        return null;
    }
  };
  
  return (
    <div className="container mx-auto px-4 py-8">
      <button
        onClick={() => onNavigate('dashboard')}
        className="flex items-center text-blue-600 hover:text-blue-800 mb-6"
      >
        ← Zurück zum Dashboard
      </button>
      
      <h1 className="text-3xl font-bold text-gray-900 mb-6">Neues Angebot erstellen</h1>
      <p className="text-gray-600 mb-8">
        Unser KI-Assistent hilft Ihnen bei der Erstellung eines professionellen Kostenvoranschlags
      </p>
      
      {/* Progress Steps */}
      <div className="mb-8">
        <div className="flex items-center justify-between">
          {[1, 2, 3, 4].map((step) => (
            <div key={step} className="flex flex-col items-center">
              <div
                className={`w-10 h-10 rounded-full flex items-center justify-center ${
                  currentStep === step
                    ? 'bg-blue-600 text-white'
                    : currentStep > step
                    ? 'bg-green-500 text-white'
                    : 'bg-gray-200 text-gray-600'
                }`}
              >
                {currentStep > step ? '✓' : step}
              </div>
              <span className="text-sm mt-2 text-gray-600">
                {step === 1 && 'Projektdaten'}
                {step === 2 && 'Kundendaten'}
                {step === 3 && 'Dokumente'}
                {step === 4 && 'Bestätigung'}
              </span>
            </div>
          ))}
        </div>
      </div>
      
      {/* Form Content */}
      <div className="bg-white rounded-lg shadow-md p-6 mb-6">
        {renderStepContent()}
      </div>
      
      {/* Navigation Buttons */}
      <div className="flex justify-between">
        {currentStep > 1 ? (
          <button
            onClick={handlePrevStep}
            className="bg-gray-200 text-gray-800 py-2 px-6 rounded-lg font-medium hover:bg-gray-300 transition-colors"
          >
            Zurück
          </button>
        ) : (
          <div></div>
        )}
        
        {currentStep < 4 ? (
          <button
            onClick={handleNextStep}
            disabled={!validateStep()}
            className={`bg-blue-600 text-white py-2 px-6 rounded-lg font-medium hover:bg-blue-700 transition-colors ${
              !validateStep() ? 'opacity-50 cursor-not-allowed' : ''
            }`}
          >
            Weiter
          </button>
        ) : (
          <button
            onClick={handleSubmit}
            disabled={loading}
            className={`bg-green-600 text-white py-2 px-6 rounded-lg font-medium hover:bg-green-700 transition-colors ${
              loading ? 'opacity-50 cursor-not-allowed' : ''
            }`}
          >
            {loading ? (
              <span className="flex items-center">
                <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                KI analysiert Daten...
              </span>
            ) : (
              <span className="flex items-center">
                🚀 Angebot erstellen
              </span>
            )}
          </button>
        )}
      </div>
    </div>
  );
};

export default QuoteCreator;

