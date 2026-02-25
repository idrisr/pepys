Backend (Python): pikepdf to walk objects/xref, decode streams (when possible), extract pages/resources, output JSON (objects, refs, types, stream_len, maybe filtered_preview).

Frontend: React + Cytoscape.js (or D3) to render an object graph; click node → show dict keys, raw/decoded stream preview, cross-refs.

Add search: “/Type /XObject”, “/Font”, “/Annot”, object id.
