import React from "react";

function Section({ title, children }) {
  return (
    <section className="panel-section">
      <h3>{title}</h3>
      {children}
    </section>
  );
}

export default function Inspector({ meta, detail, pages, loading, onSelectRef }) {
  if (loading) {
    return (
      <div className="inspector">
        <div className="panel-title">Object Inspector</div>
        <div className="loading-card">Loading object details...</div>
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="inspector">
        <div className="panel-title">Object Inspector</div>
        <div className="panel-summary">
          <h2>PDF Overview</h2>
          <p className="muted">
            Upload a PDF to explore its object graph. Click any node to inspect
            dictionaries, references, and stream previews.
          </p>
        </div>
        {meta && (
          <div className="meta-grid">
            <div>
              <span className="meta-label">File</span>
              <span className="meta-value">{meta.filename}</span>
            </div>
            <div>
              <span className="meta-label">Pages</span>
              <span className="meta-value">{meta.page_count}</span>
            </div>
            <div>
              <span className="meta-label">Objects</span>
              <span className="meta-value">{meta.object_count}</span>
            </div>
            <div>
              <span className="meta-label">PDF Version</span>
              <span className="meta-value">{meta.pdf_version || "-"}</span>
            </div>
          </div>
        )}
        {pages && pages.length > 0 && (
          <Section title="Pages">
            <div className="page-list">
              {pages.slice(0, 8).map((page) => (
                <div key={page.page} className="page-row">
                  <span>Page {page.page}</span>
                  <span className="muted">{page.obj_id || "no id"}</span>
                </div>
              ))}
            </div>
          </Section>
        )}
      </div>
    );
  }

  return (
    <div className="inspector">
      <div className="panel-title">Object Inspector</div>
      <div className="panel-summary">
        <h2>{detail.label}</h2>
        <p className="muted">{detail.id}</p>
        <div className="badge-row">
          <span className="badge">{detail.type}</span>
          {detail.subtype && <span className="badge">{detail.subtype}</span>}
          {detail.has_stream && <span className="badge accent">Stream</span>}
        </div>
      </div>

      <Section title="References">
        {detail.refs && detail.refs.length > 0 ? (
          <div className="ref-list">
            {detail.refs.map((ref) => (
              <button
                key={`${ref.obj_id}-${ref.path}`}
                className="ref-chip"
                onClick={() => onSelectRef(ref.obj_id)}
                type="button"
              >
                <span>{ref.obj_id}</span>
                <span className="muted">{ref.path}</span>
              </button>
            ))}
          </div>
        ) : (
          <p className="muted">No references found.</p>
        )}
      </Section>

      <Section title="Dictionary">
        {detail.dict ? (
          <pre className="code-block">
            {JSON.stringify(detail.dict, null, 2)}
          </pre>
        ) : (
          <p className="muted">No dictionary data.</p>
        )}
      </Section>

      {detail.stream && (
        <Section title="Stream Preview">
          <div className="stream-meta">
            <div>
              <span className="meta-label">Filters</span>
              <span className="meta-value">
                {detail.stream.filters?.length
                  ? detail.stream.filters.join(", ")
                  : "none"}
              </span>
            </div>
            <div>
              <span className="meta-label">Length</span>
              <span className="meta-value">{detail.stream.length ?? "-"}</span>
            </div>
            <div>
              <span className="meta-label">Encoding</span>
              <span className="meta-value">
                {detail.stream.preview_encoding || "-"}
              </span>
            </div>
          </div>
          <pre className="code-block">
            {detail.stream.preview || "(empty stream)"}
          </pre>
        </Section>
      )}
    </div>
  );
}
