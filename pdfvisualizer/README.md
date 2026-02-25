# PDF Structure Visualizer

This folder contains a Flask API and a React + Vite frontend for exploring the
internal structure of PDF files.

## Single URL (recommended)
Build the frontend and serve it from Flask:
```bash
cd pdfvisualizer
nix run .#pdfvisualizer-app
```
Open `http://127.0.0.1:8001`.

## Backend (Flask API)
```bash
cd pdfvisualizer/api
PDFVIZ_PORT=8001 python app.py
```

Environment variables
- `PDFVIZ_PORT` (default: 8001)
- `PDFVIZ_MAX_MB` (default: 100)
- `PDFVIZ_CORS_ORIGIN` (default: `*`)
- `PDFVIZ_STORAGE_DIR` (default: temp dir under `/tmp/pdfvisualizer`)

## Frontend (React + Vite)
```bash
cd pdfvisualizer/web
npm install
npm run dev
```

## Nix helpers
```bash
cd pdfvisualizer
nix run .#pdfvisualizer-api   # API only
nix run .#pdfvisualizer-web   # UI only (static server on :5173)
nix run .#pdfvisualizer-dev   # API + UI dev server (requires npm install in web/)
```

Optional: point to a remote API
```bash
VITE_API_BASE="https://your-api-host" npm run dev
```

## Notes
- Upload a PDF in the UI to generate the object graph.
- Click nodes to inspect dictionaries, references, and stream previews.
