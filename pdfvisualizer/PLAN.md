# PDF Structure Visualizer: Planning Doc

## Goals
- Help users see the internal object graph of a PDF (xref table, objects, streams, pages, and resources).
- Make object inspection fast: click a node and view its dictionary, refs, and stream preview.
- Provide search and filtering for common patterns (/Type, /XObject, /Font, /Annot, object id).

## Non-goals (for MVP)
- Full PDF rendering engine or spec-complete decoding of every stream filter.
- Editing PDFs or writing changes back to disk.
- Heavy authentication or multi-tenant account management.

## High-level Architecture
- Backend parses PDFs into a graph model and serves JSON.
- Frontend renders the graph, lists pages/resources, and shows object details.
- Optional: page thumbnails via PDF.js for spatial context.

## Proposed Libraries
Backend (Python)
- PDF parsing: pikepdf (qpdf-backed), fallback to pypdf for edge cases.
- API: Flask (aligned with the existing stack in this repo).
- Background processing: simple in-process worker for MVP; move to RQ/Celery if needed.
- Data: in-memory or temp-file JSON; optional SQLite cache per PDF id.

Frontend (Web)
- Framework: React + Vite.
- Graph: Cytoscape.js (good for large graphs, built-in layout algorithms).
- PDF preview: PDF.js for page thumbnails (optional).
- UI: Tailwind or vanilla CSS; keep custom styling minimal.

## Data Model (API JSON)
Core entities
- pdf: { id, filename, size, page_count, object_count, created_at }
- node: { id: "12 0 R", type, subtype, label, size, has_stream }
- edge: { from, to, via_key }
- object_detail: { id, dict, refs, stream: { filters, length, decoded_preview } }

Graph payload
- nodes: [node]
- edges: [edge]
- stats: { type_counts, stream_count, max_degree }

## Endpoints (Draft)
- POST /api/pdfs
  - multipart upload; returns { id }
- GET /api/pdfs/{id}
  - summary metadata
- GET /api/pdfs/{id}/status
  - parse progress, errors
- GET /api/pdfs/{id}/graph?limit=&offset=&type=
  - nodes/edges with optional filters or pagination
- GET /api/pdfs/{id}/object/{obj_id}
  - full object detail and decoded stream preview
- GET /api/pdfs/{id}/object/{obj_id}/stream
  - raw or decoded stream bytes (limited, text-safe)
- GET /api/pdfs/{id}/xref
  - xref table sections, object offsets (if available)
- GET /api/pdfs/{id}/pages
  - list of pages and their resource references
- GET /api/pdfs/{id}/search?q=
  - query by object id, key, or regex-like /Type patterns
- DELETE /api/pdfs/{id}
  - cleanup temp data

## UX Flow (MVP)
1. Landing page: drag-and-drop PDF upload + size limits + sample file.
2. Processing state: progress indicator with counts discovered (objects, streams, pages).
3. Graph view: zoom/pan, layout selector, filter by type/subtype.
4. Inspector panel: shows object dict, refs, stream preview, and linked objects.
5. Search bar: jump to object id or filter by /Type.
6. Pages tab: list pages and their resources; click to highlight related nodes.

## UX Details
- Keep graph readable: collapse low-signal nodes by default, expand on click.
- Color by type (Page, XObject, Font, Annot, Stream).
- Show degree and stream length in tooltips.
- Provide “focus mode” for a selected node and its neighbors.

## Performance and Safety
- Enforce max upload size (e.g., 100MB) and timeouts on parsing.
- Limit stream previews (e.g., first 2-8KB) and mark binary content.
- Cache graph JSON on disk; reuse across requests.
- Sanitize filenames and isolate temp storage per PDF id.

## Milestones
- M1: upload + parse + basic graph + object inspector.
- M2: search + filters + page/resource list.
- M3: PDF.js thumbnails + refined layouts.

## Open Decisions
- Storage strategy for parsed results (in-memory vs temp JSON vs SQLite).
- Storage strategy for parsed results (in-memory vs temp JSON vs SQLite).
- Layout defaults for large PDFs (breadth-first vs concentric).
