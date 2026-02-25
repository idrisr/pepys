import { useRef } from "react";

export default function UploadCard({ onUpload, busy, error }) {
  const inputRef = useRef(null);

  const handleSelect = (event) => {
    const file = event.target.files?.[0];
    if (file) {
      onUpload(file);
      event.target.value = "";
    }
  };

  const handleDrop = (event) => {
    event.preventDefault();
    const file = event.dataTransfer.files?.[0];
    if (file) {
      onUpload(file);
    }
  };

  return (
    <div
      className="upload-card"
      onDrop={handleDrop}
      onDragOver={(event) => event.preventDefault()}
    >
      <div className="upload-title">Drop a PDF to start exploring</div>
      <p className="muted">
        Visualize the object graph, inspect streams, and trace references.
      </p>
      <div className="upload-actions">
        <button
          className="primary"
          type="button"
          onClick={() => inputRef.current?.click()}
          disabled={busy}
        >
          {busy ? "Uploading..." : "Choose PDF"}
        </button>
        <span className="muted">Max 100MB</span>
      </div>
      {error && <div className="error-banner">{error}</div>}
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf"
        onChange={handleSelect}
        hidden
      />
    </div>
  );
}
