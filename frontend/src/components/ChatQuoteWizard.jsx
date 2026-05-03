import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import apiClient from '../services/apiClient';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Card } from './ui/card';
import { ScrollArea } from './ui/scroll-area';
import { Loader2, Send, Upload, FileText } from 'lucide-react';

const ChatQuoteWizard = () => {
  const { isAuthenticated, loading: authLoading } = useAuth();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [conversationHistory, setConversationHistory] = useState([]);
  const [currentQuote, setCurrentQuote] = useState(null);
  const [showCustomerForm, setShowCustomerForm] = useState(false);
  const [customerData, setCustomerData] = useState({
    customer_name: '',
    customer_address: '',
    customer_email: '',
    customer_phone: ''
  });
  const [uploadedDocuments, setUploadedDocuments] = useState([]);
  const scrollRef = useRef(null);
  const fileInputRef = useRef(null);

  // Scroll to bottom when messages change
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleInputChange = (e) => {
    setInputValue(e.target.value);
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setLoading(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append('file', file);
      if (currentQuote?.id) {
        formData.append('quote_id', currentQuote.id);
      }

      // Upload file
      const response = await apiClient.uploadDocument(formData);

      // Dokument und Analyse im State speichern
      setUploadedDocuments(prev => [...prev, response]);

      // Add AI response to chat (mit Analyse-Feedback)
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: response.analysis_result && response.analysis_result.extracted_text
          ? `Dokument analysiert: ${response.analysis_result.extracted_text}`
          : 'Dokument wurde analysiert. Ich werde die Informationen in die Angebotserstellung einbeziehen.',
        type: 'text',
        analysis: response.analysis_result
      }]);

      // Update conversation history
      setConversationHistory(prev => [...prev, {
        role: 'user',
        content: `Datei hochgeladen: ${file.name}`,
        timestamp: new Date().toISOString()
      }, {
        role: 'assistant',
        content: response.analysis_result && response.analysis_result.extracted_text
          ? `Dokument analysiert: ${response.analysis_result.extracted_text}`
          : 'Dokument wurde analysiert. Ich werde die Informationen in die Angebotserstellung einbeziehen.',
        timestamp: new Date().toISOString()
      }]);

    } catch (err) {
      setError('Fehler beim Hochladen der Datei: ' + (err.message || 'Unbekannter Fehler'));
      // Add error message to chat
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Entschuldigung, beim Hochladen der Datei ist ein Fehler aufgetreten.',
        type: 'error'
      }]);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!inputValue.trim() || loading) return;

    const userMessage = inputValue.trim();
    setInputValue('');
    setLoading(true);
    setError(null);

    try {
      // Add user message to chat
      setMessages(prev => [...prev, {
        role: 'user',
        content: userMessage,
        type: 'text'
      }]);

      const updatedHistory = [...conversationHistory, {
        role: 'user',
        content: userMessage,
        timestamp: new Date().toISOString()
      }];
      setConversationHistory(updatedHistory);

      const attachments = uploadedDocuments
        .filter((doc) => doc.file_path)
        .map((doc) => ({
          file_path: doc.file_path,
          file_name: doc.original_filename || doc.filename,
          type: doc.mime_type?.startsWith('image/') ? 'image' : 'document',
        }));
      const response = await apiClient.chatWithAgent(userMessage, attachments);
      const assistantText = response.humanized_message || response.final_message || 'Keine Antwort generiert.';
      const producedQuote = response.quote_id || response.pdf_url || response.quote_number;

      setMessages(prev => [...prev, {
        role: 'assistant',
        content: assistantText,
        type: 'text',
        quote: producedQuote ? {
          id: response.quote_id,
          number: response.quote_number,
          pdfUrl: response.pdf_url,
        } : null,
      }]);

      if (producedQuote) {
        setCurrentQuote({
          id: response.quote_id,
          number: response.quote_number,
          pdfUrl: response.pdf_url,
        });
      }

      setConversationHistory(prev => [...prev, {
        role: 'assistant',
        content: assistantText,
        timestamp: new Date().toISOString()
      }]);

    } catch (err) {
      setError('Fehler bei der Verarbeitung: ' + (err.message || 'Unbekannter Fehler'));
      
      // Add error message to chat
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Entschuldigung, bei der Verarbeitung ist ein Fehler aufgetreten.',
        type: 'error'
      }]);
    } finally {
      setLoading(false);
    }
  };

  const handleCustomerInputChange = (e) => {
    const { name, value } = e.target;
    setCustomerData((prev) => ({ ...prev, [name]: value }));
  };

  const handleOpenAgentPdf = async (pdfUrl, filename = 'kostenvoranschlag.pdf') => {
    try {
      const blob = await apiClient.fetchAgentPdf(pdfUrl);
      const objectUrl = URL.createObjectURL(blob);
      const opened = window.open(objectUrl, '_blank', 'noopener,noreferrer');
      if (!opened) {
        const link = document.createElement('a');
        link.href = objectUrl;
        link.download = filename;
        link.click();
      }
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000);
    } catch (err) {
      setError(err.message || 'PDF konnte nicht geöffnet werden');
    }
  };

  const handleCustomerFormSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      // Sammle alle Analyse-Resultate der hochgeladenen Dokumente
      const documentAnalyses = uploadedDocuments
        .map(doc => doc.analysis_result)
        .filter(Boolean);
      // Generate quote with customer data and document analyses
      const quoteData = await apiClient.generateQuoteFromConversation({
        project_data: {
          description: messages.find(m => m.role === 'user')?.content || '',
          document_analyses: documentAnalyses
        },
        answers: conversationHistory.filter(m => m.role === 'user').map(m => ({
          question: m.content,
          answer: m.content
        })),
        conversation_history: conversationHistory,
        ...customerData
      });
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Kostenvoranschlag wurde erstellt! Sie werden zur Detailansicht weitergeleitet.',
        type: 'text'
      }]);
      setConversationHistory(prev => [...prev, {
        role: 'assistant',
        content: 'Kostenvoranschlag wurde erstellt! Sie werden zur Detailansicht weitergeleitet.',
        timestamp: new Date().toISOString()
      }]);
      setCurrentQuote(quoteData);
      setShowCustomerForm(false);
      
      // Navigate to quote detail view
      if (quoteData.quote && quoteData.quote.id) {
        navigate(`/quotes/${quoteData.quote.id}`);
      }
    } catch (err) {
      setError('Fehler beim Erstellen des Kostenvoranschlags: ' + (err.message || 'Unbekannter Fehler'));
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Entschuldigung, beim Erstellen des Kostenvoranschlags ist ein Fehler aufgetreten.',
        type: 'error'
      }]);
    } finally {
      setLoading(false);
    }
  };

  // Authentifizierungsprüfung
  if (authLoading) {
    return <div>Lade Authentifizierung...</div>;
  }
  if (!isAuthenticated) {
    return <div>Bitte zuerst einloggen.</div>;
  }

  return (
    <div className="flex flex-col h-full max-w-4xl mx-auto p-4">
      <div className="flex-1 flex flex-col">
        {/* Chat messages */}
        <ScrollArea ref={scrollRef} className="flex-1 p-4">
          <div className="space-y-4">
            {messages.map((message, index) => (
              <Card
                key={index}
                className={`p-4 ${
                  message.role === 'user' 
                    ? 'bg-blue-50 ml-auto' 
                    : 'bg-white'
                } max-w-[80%]`}
              >
                {message.type === 'file' ? (
                  <div className="flex items-center space-x-2">
                    <FileText className="h-4 w-4" />
                    <span>{message.content}</span>
                  </div>
                ) : (
                  <div className="space-y-3">
                    <p className={message.type === 'error' ? 'text-red-500' : ''}>
                      {message.content}
                    </p>
                    {message.quote && (
                      <div className="rounded-lg border bg-green-50 p-3 text-sm text-green-900">
                        <p className="font-medium">
                          Angebot {message.quote.number || `#${message.quote.id}`} ist fertig.
                        </p>
                        <div className="mt-3 flex flex-wrap gap-2">
                          {message.quote.pdfUrl && (
                            <Button
                              type="button"
                              size="sm"
                              onClick={() => handleOpenAgentPdf(message.quote.pdfUrl, `${message.quote.number || 'kostenvoranschlag'}.pdf`)}
                            >
                              PDF öffnen
                            </Button>
                          )}
                          {message.quote.id && (
                            <Button
                              type="button"
                              size="sm"
                              variant="outline"
                              onClick={() => window.location.assign(`/quotes/${message.quote.id}`)}
                            >
                              Angebot anzeigen
                            </Button>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </Card>
            ))}
          </div>
        </ScrollArea>

        {/* Input area */}
        <div className="border-t p-4">
          <form onSubmit={handleSubmit} className="flex space-x-2">
            <Input
              value={inputValue}
              onChange={handleInputChange}
              placeholder="Beschreiben Sie Ihr Projekt..."
              disabled={loading}
              className="flex-1"
            />
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileUpload}
              className="hidden"
              accept="image/*, application/pdf"
            />
            <Button
              type="button"
              variant="outline"
              onClick={() => fileInputRef.current?.click()}
              disabled={loading}
            >
              <Upload className="h-4 w-4" />
            </Button>
            <Button type="submit" disabled={loading || !inputValue.trim()}>
              {loading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Send className="h-4 w-4" />
              )}
            </Button>
          </form>
        </div>

        {/* Kundenformular */}
        {showCustomerForm && !currentQuote && (
          <div className="p-4 border-t bg-gray-50 rounded shadow mt-4">
            <form onSubmit={handleCustomerFormSubmit} className="space-y-4 max-w-lg mx-auto">
              <h2 className="text-lg font-semibold mb-2">Ihre Kontaktdaten für das Angebot</h2>
              <div>
                <label className="block text-sm font-medium mb-1">Name *</label>
                <Input
                  name="customer_name"
                  value={customerData.customer_name}
                  onChange={handleCustomerInputChange}
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Adresse *</label>
                <Input
                  name="customer_address"
                  value={customerData.customer_address}
                  onChange={handleCustomerInputChange}
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">E-Mail *</label>
                <Input
                  name="customer_email"
                  type="email"
                  value={customerData.customer_email}
                  onChange={handleCustomerInputChange}
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Telefon *</label>
                <Input
                  name="customer_phone"
                  type="tel"
                  value={customerData.customer_phone}
                  onChange={handleCustomerInputChange}
                  required
                />
              </div>
              <div className="flex space-x-2 mt-4">
                <Button type="submit" disabled={loading} className="w-full">
                  {loading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                  Angebot anfordern
                </Button>
                <Button type="button" variant="outline" onClick={() => setShowCustomerForm(false)} disabled={loading}>
                  Abbrechen
                </Button>
              </div>
            </form>
          </div>
        )}

        {/* Error message */}
        {error && (
          <div className="p-4 text-red-500 text-sm">
            {error}
          </div>
        )}

        {currentQuote && (
          <div className="p-4 border-t bg-white">
            <div className="max-w-xl mx-auto rounded-lg border p-4">
              <p className="font-medium">
                Letztes Agent-Ergebnis: {currentQuote.number || `Angebot #${currentQuote.id}`}
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                {currentQuote.pdfUrl && (
                  <Button
                    type="button"
                    onClick={() => handleOpenAgentPdf(currentQuote.pdfUrl, `${currentQuote.number || 'kostenvoranschlag'}.pdf`)}
                  >
                    PDF öffnen
                  </Button>
                )}
                {currentQuote.id && (
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => window.location.assign(`/quotes/${currentQuote.id}`)}
                  >
                    Im Dashboard anzeigen
                  </Button>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default ChatQuoteWizard; 