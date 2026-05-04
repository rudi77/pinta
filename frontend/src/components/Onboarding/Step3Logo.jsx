import React, { useRef } from 'react';
import { Button } from '../ui/button';

const ACCEPT = 'image/png,image/jpeg,image/webp,image/svg+xml';

const Step3Logo = ({ file, onChange, onBack, onFinish, submitting }) => {
  const inputRef = useRef(null);

  const handleFile = (f) => {
    if (!f) {
      onChange(null);
      return;
    }
    if (f.size > 1024 * 1024) {
      alert('Logo darf max. 1 MB groß sein.');
      return;
    }
    onChange(f);
  };

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold">Dein Logo (optional)</h2>
      <p className="text-sm text-gray-600">
        Wenn du ein Logo hochlädst, erscheint es auf jedem Angebots-PDF.
      </p>

      <div className="border-2 border-dashed border-gray-300 rounded-md p-6 text-center">
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPT}
          className="hidden"
          onChange={(e) => handleFile(e.target.files?.[0] || null)}
        />
        {file ? (
          <div className="space-y-2">
            <p className="text-sm text-gray-700">
              Ausgewählt: <strong>{file.name}</strong>
            </p>
            <Button
              type="button"
              variant="outline"
              onClick={() => onChange(null)}
            >
              Entfernen
            </Button>
          </div>
        ) : (
          <Button
            type="button"
            variant="outline"
            onClick={() => inputRef.current?.click()}
          >
            Datei auswählen (PNG, JPG, WebP, SVG)
          </Button>
        )}
      </div>

      <div className="flex justify-between pt-2">
        <Button type="button" variant="outline" onClick={onBack} disabled={submitting}>
          Zurück
        </Button>
        <Button type="button" onClick={onFinish} disabled={submitting}>
          {submitting ? 'Speichern…' : file ? 'Fertig' : 'Überspringen & Fertig'}
        </Button>
      </div>
    </div>
  );
};

export default Step3Logo;
