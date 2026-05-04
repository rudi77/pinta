import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import apiClient from '../services/apiClient';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Card } from './ui/card';
import { ScrollArea } from './ui/scroll-area';
import { Loader2, Send, Upload, FileText } from 'lucide-react';

const QuoteChat = () => {
  const { isAuthenticated, loading: authLoading } = useAuth();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [currentQuote, setCurrentQuote] = useState(null);
  const [uploadedDocuments, setUploadedDocuments] = useState([]);
  const scrollRef = useRef(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleInputChange = (e) => {
    setInputValue(e.target.value);
  };

  const handleFileUpload = async (e) => {
    const files = Array.from(e.target.files || []);
    if (files.length === 0) return;

    setLoading(true);
    setError(null);

    try {
      for (const file of files) {
        const formData = new FormData();
        formData.append('file', file);
        if (currentQuote?.id) {
          formData.append('quote_id', currentQuote.id);
        }

        const response = await apiClient.uploadDocument(formData);
        setUploadedDocuments((prev) => [...prev, response]);

        const assistantText =
          response.analysis_result && response.analysis_result.extracted_text
            ? `Datei "${file.name}" eingelesen: ${response.analysis_result.extracted_text}`
            : `Datei "${file.name}" eingelesen. Ich beziehe sie in das Angebot mit ein.`;

        setMessages((prev) => [
          ...prev,
          { role: 'user', content: `📎 ${file.name}`, type: 'file' },
          { role: 'assistant', content: assistantText, type: 'text' },
        ]);
      }
    } catch (err) {
      setError('Fehler beim Hochladen: ' + (err.message || 'Unbekannter Fehler'));
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: 'Beim Hochladen ist ein Fehler aufgetreten.',
          type: 'error',
        },
      ]);
    } finally {
      setLoading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
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
      setMessages((prev) => [
        ...prev,
        { role: 'user', content: userMessage, type: 'text' },
      ]);

      const attachments = uploadedDocuments
        .filter((doc) => doc.file_path)
        .map((doc) => ({
          file_path: doc.file_path,
          file_name: doc.original_filename || doc.filename,
          type: doc.mime_type?.startsWith('image/') ? 'image' : 'document',
        }));

      const response = await apiClient.chatWithAgent(userMessage, attachments);
      const assistantText =
        response.humanized_message ||
        response.final_message ||
        'Keine Antwort erhalten.';
      const producedQuote =
        response.quote_id || response.pdf_url || response.quote_number;

      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: assistantText,
          type: 'text',
          quote: producedQuote
            ? {
                id: response.quote_id,
                number: response.quote_number,
                pdfUrl: response.pdf_url,
              }
            : null,
        },
      ]);

      if (producedQuote) {
        setCurrentQuote({
          id: response.quote_id,
          number: response.quote_number,
          pdfUrl: response.pdf_url,
        });
      }
    } catch (err) {
      setError('Fehler bei der Verarbeitung: ' + (err.message || 'Unbekannter Fehler'));
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: 'Bei der Verarbeitung ist ein Fehler aufgetreten.',
          type: 'error',
        },
      ]);
    } finally {
      setLoading(false);
    }
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

  if (authLoading) {
    return <div>Lade Authentifizierung...</div>;
  }
  if (!isAuthenticated) {
    return <div>Bitte zuerst anmelden.</div>;
  }

  return (
    <div className="flex flex-col h-full max-w-4xl mx-auto p-4">
      <div className="flex-1 flex flex-col">
        <ScrollArea ref={scrollRef} className="flex-1 p-4">
          <div className="space-y-4">
            {messages.length === 0 && (
              <Card className="p-4 bg-blue-50 max-w-[80%]">
                <p className="text-sm text-gray-700">
                  Beschreibe dein Projekt — z.&nbsp;B. „Wohnzimmer 25 m², Decke
                  und Wände, weiß, Familie Schmidt". Du kannst Fotos oder
                  PDF-Pläne mitschicken.
                </p>
              </Card>
            )}
            {messages.map((message, index) => (
              <Card
                key={index}
                className={`p-4 ${
                  message.role === 'user' ? 'bg-blue-50 ml-auto' : 'bg-white'
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
                          Angebot{' '}
                          {message.quote.number ||
                            `#${message.quote.id}`}{' '}
                          ist fertig.
                        </p>
                        <div className="mt-3 flex flex-wrap gap-2">
                          {message.quote.pdfUrl && (
                            <Button
                              type="button"
                              size="sm"
                              onClick={() =>
                                handleOpenAgentPdf(
                                  message.quote.pdfUrl,
                                  `${message.quote.number || 'kostenvoranschlag'}.pdf`,
                                )
                              }
                            >
                              PDF öffnen
                            </Button>
                          )}
                          {message.quote.id && (
                            <Button
                              type="button"
                              size="sm"
                              variant="outline"
                              onClick={() => navigate(`/quotes/${message.quote.id}`)}
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

        <div className="border-t p-4">
          <form onSubmit={handleSubmit} className="flex space-x-2">
            <Input
              value={inputValue}
              onChange={handleInputChange}
              placeholder="Projekt beschreiben…"
              disabled={loading}
              className="flex-1"
            />
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileUpload}
              className="hidden"
              accept="image/*,application/pdf"
              multiple
            />
            <Button
              type="button"
              variant="outline"
              onClick={() => fileInputRef.current?.click()}
              disabled={loading}
              title="Foto oder PDF anhängen"
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

        {error && (
          <div className="p-4 text-red-500 text-sm">{error}</div>
        )}

        {currentQuote && (
          <div className="p-4 border-t bg-white">
            <div className="max-w-xl mx-auto rounded-lg border p-4">
              <p className="font-medium">
                Letztes Angebot:{' '}
                {currentQuote.number || `#${currentQuote.id}`}
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                {currentQuote.pdfUrl && (
                  <Button
                    type="button"
                    onClick={() =>
                      handleOpenAgentPdf(
                        currentQuote.pdfUrl,
                        `${currentQuote.number || 'kostenvoranschlag'}.pdf`,
                      )
                    }
                  >
                    PDF öffnen
                  </Button>
                )}
                {currentQuote.id && (
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => navigate(`/quotes/${currentQuote.id}`)}
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

export default QuoteChat;
