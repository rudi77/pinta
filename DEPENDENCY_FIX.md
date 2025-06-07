# Dependency-Fehlerbehebung

## Problem behoben! ✅

Die Dependency-Konflikte wurden in der neuen Version behoben:

### Änderungen:
- **date-fns**: Downgrade von 4.1.0 → 3.6.0 (kompatibel mit react-day-picker)
- **react-day-picker**: Upgrade von 8.10.1 → 9.4.3 (unterstützt date-fns 3.x)
- **React**: Downgrade von 19.1.0 → 18.3.1 (stabiler für Produktion)
- **packageManager**: Geändert zu npm@9.6.5

## Installation (Windows):

### Option 1: Standard-Installation
```powershell
cd frontend
npm install
```

### Option 2: Falls weiterhin Probleme auftreten
```powershell
cd frontend
npm install --legacy-peer-deps
```

### Option 3: Cache leeren und neu installieren
```powershell
cd frontend
npm cache clean --force
rm -rf node_modules
rm package-lock.json
npm install
```

### Option 4: Yarn verwenden (Alternative)
```powershell
cd frontend
npm install -g yarn
yarn install
```

## Backend-Installation (Windows):

```powershell
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## Starten:

### Backend:
```powershell
cd backend
venv\Scripts\activate
python src/main.py
```

### Frontend:
```powershell
cd frontend
npm run dev
```

## Bei weiteren Problemen:

1. **Node.js Version prüfen**: Mindestens Node.js 18.x erforderlich
2. **npm Version updaten**: `npm install -g npm@latest`
3. **Windows-spezifische Tools**: `npm install -g windows-build-tools` (falls erforderlich)

Das korrigierte Projekt sollte jetzt ohne Dependency-Konflikte installieren! 🎉

