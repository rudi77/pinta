import React, { useRef, useState } from 'react';
import { Card } from '../ui/card';
import { Button } from '../ui/button';
import apiClient from '../../services/apiClient';

const ACCEPT = 'image/png,image/jpeg,image/webp,image/svg+xml';

const LogoSection = ({ profile, onSaved }) => {
  const inputRef = useRef(null);
  const [uploading, setUploading] = useState(false);
  const [removing, setRemoving] = useState(false);
  const [status, setStatus] = useState(null);

  const handleFile = async (file) => {
    if (!file) return;
    if (file.size > 1024 * 1024) {
      setStatus({ type: 'err', text: 'Logo darf max. 1 MB groß sein.' });
      return;
    }
    setUploading(true);
    setStatus(null);
    try {
      await apiClient.uploadLogo(file);
      setStatus({ type: 'ok', text: 'Logo aktualisiert.' });
      await onSaved?.();
    } catch (err) {
      setStatus({ type: 'err', text: err.message || 'Upload fehlgeschlagen' });
    } finally {
      setUploading(false);
      if (inputRef.current) inputRef.current.value = '';
    }
  };

  const handleRemove = async () => {
    setRemoving(true);
    setStatus(null);
    try {
      await apiClient.deleteUserLogo();
      setStatus({ type: 'ok', text: 'Logo entfernt.' });
      await onSaved?.();
    } catch (err) {
      setStatus({ type: 'err', text: err.message || 'Entfernen fehlgeschlagen' });
    } finally {
      setRemoving(false);
    }
  };

  const hasLogo = Boolean(profile.logo_path);

  return (
    <Card className="p-6">
      <div className="space-y-4">
        <div>
          <h2 className="text-lg font-semibold">Logo</h2>
          <p className="text-sm text-gray-600">
            Erscheint im Kopfbereich jedes generierten PDF-Angebots. Optional.
          </p>
        </div>

        <input
          ref={inputRef}
          type="file"
          accept={ACCEPT}
          className="hidden"
          onChange={(e) => handleFile(e.target.files?.[0] || null)}
        />

        {hasLogo ? (
          <div className="rounded-md border border-gray-200 bg-gray-50 p-3 flex items-center justify-between gap-4">
            <div className="text-sm text-gray-700 break-all">
              <p className="font-medium">Aktuelles Logo</p>
              <code className="text-xs text-gray-500">{profile.logo_path}</code>
            </div>
            <div className="flex flex-col gap-2 shrink-0">
              <Button
                size="sm"
                variant="outline"
                onClick={() => inputRef.current?.click()}
                disabled={uploading || removing}
              >
                {uploading ? 'Lade…' : 'Ersetzen'}
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={handleRemove}
                disabled={uploading || removing}
              >
                {removing ? 'Entferne…' : 'Entfernen'}
              </Button>
            </div>
          </div>
        ) : (
          <div className="rounded-md border-2 border-dashed border-gray-300 p-6 text-center">
            <Button
              type="button"
              variant="outline"
              onClick={() => inputRef.current?.click()}
              disabled={uploading}
            >
              {uploading ? 'Lade…' : 'Logo hochladen (PNG, JPG, WebP, SVG)'}
            </Button>
            <p className="mt-2 text-xs text-gray-500">Max 1 MB</p>
          </div>
        )}

        {status && (
          <p
            className={`text-sm ${
              status.type === 'ok' ? 'text-green-700' : 'text-red-600'
            }`}
          >
            {status.text}
          </p>
        )}
      </div>
    </Card>
  );
};

export default LogoSection;
