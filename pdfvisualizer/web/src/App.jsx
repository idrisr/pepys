import { useState } from "react";
import {
  getGraph,
  getObjectDetail,
  getPages,
  getPdfMeta,
  deletePdf,
  searchObjects,
  uploadPdf,
} from "./api.js";
import Inspector from "./components/Inspector.jsx";
import PageReader from "./components/PageReader.jsx";
import UploadCard from "./components/UploadCard.jsx";

export default function App() {
  const [pdfId, setPdfId] = useState(null);
  const [meta, setMeta] = useState(null);
  const [graph, setGraph] = useState({ nodes: [], edges: [], stats: {} });
  const [pages, setPages] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState([]);

  const resetPdfState = () => {
    setPdfId(null);
    setMeta(null);
    setGraph({ nodes: [], edges: [], stats: {} });
    setPages([]);
    setSelectedId(null);
    setDetail(null);
    setDetailLoading(false);
    setSearchQuery("");
    setSearchResults([]);
  };

  const handleUpload = async (file) => {
    setBusy(true);
    setError(null);
    setSearchResults([]);
    setSelectedId(null);
    setDetail(null);

    try {
      const upload = await uploadPdf(file);
      setPdfId(upload.id);
      setMeta(upload.meta);

      const [graphData, pagesData, metaData] = await Promise.all([
        getGraph(upload.id),
        getPages(upload.id),
        getPdfMeta(upload.id),
      ]);

      setGraph(graphData);
      setPages(pagesData.pages || []);
      setMeta(metaData);
    } catch (err) {
      setError(err.message || "Upload failed");
    } finally {
      setBusy(false);
    }
  };

  const handleSelect = async (objId) => {
    if (!objId || !pdfId) {
      setSelectedId(null);
      setDetail(null);
      return;
    }

    setSelectedId(objId);
    setDetailLoading(true);
    setError(null);
    try {
      const detailData = await getObjectDetail(pdfId, objId);
      setDetail(detailData);
    } catch (err) {
      setError(err.message || "Failed to load object");
    } finally {
      setDetailLoading(false);
    }
  };

  const handleSearch = async (event) => {
    event.preventDefault();
    if (!pdfId || !searchQuery.trim()) {
      setSearchResults([]);
      return;
    }

    try {
      setError(null);
      const results = await searchObjects(pdfId, searchQuery.trim());
      setSearchResults(results.results || []);
      if (results.results?.length === 1) {
        handleSelect(results.results[0].id);
      }
    } catch (err) {
      setError(err.message || "Search failed");
    }
  };

  const handleRemovePdf = async () => {
    if (!pdfId) {
      return;
    }
    setBusy(true);
    setError(null);
    const currentId = pdfId;

    try {
      await deletePdf(currentId);
    } catch (err) {
      setError(err.message || "Failed to remove PDF");
    } finally {
      resetPdfState();
      setBusy(false);
    }
  };

  return (
    <div className="app-shell">
      <header className="top-bar">
        <div className="brand">
          <div>
            <h1>PDF Structure Visualizer</h1>
            <p className="muted">
              Map objects, streams, and references inside any PDF.
            </p>
          </div>
          {meta && (
            <div className="file-pill">
              <span className="file-name">{meta.filename}</span>
              <span className="muted">
                {meta.page_count} pages | {meta.object_count} objects
              </span>
              <div className="file-pill-actions">
                <button
                  className="ghost small"
                  type="button"
                  onClick={handleRemovePdf}
                  disabled={busy}
                >
                  New PDF
                </button>
              </div>
            </div>
          )}
        </div>

        <div className="controls">
          <form className="search" onSubmit={handleSearch}>
            <input
              type="search"
              placeholder="Search /Type, object id, key"
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
            />
            <button className="ghost" type="submit">
              Search
            </button>
            <button
              className="ghost"
              type="button"
              onClick={() => {
                setSelectedId(null);
                setDetail(null);
              }}
            >
              Clear selection
            </button>
          </form>

          {searchResults.length > 0 && (
            <div className="results-bar">
              {searchResults.slice(0, 8).map((result) => (
                <button
                  key={result.id}
                  className="result-chip"
                  type="button"
                  onClick={() => handleSelect(result.id)}
                >
                  {result.id}
                </button>
              ))}
              {searchResults.length > 8 && (
                <span className="muted">
                  +{searchResults.length - 8} more
                </span>
              )}
            </div>
          )}
        </div>

        {error && <div className="error-banner">{error}</div>}
      </header>

      <main className="main-grid">
        <section className="graph-panel">
          {!pdfId && (
            <div className="overlay">
              <UploadCard onUpload={handleUpload} busy={busy} error={error} />
            </div>
          )}

          {pdfId && (
            <PageReader
              pdfId={pdfId}
              pages={pages}
              graph={graph}
              selectedObjectId={selectedId}
              onSelectObject={handleSelect}
            />
          )}
        </section>

        <aside className="side-panel">
          <Inspector
            meta={meta}
            detail={detail}
            pages={pages}
            loading={detailLoading}
            onSelectRef={handleSelect}
          />
        </aside>
      </main>
    </div>
  );
}
