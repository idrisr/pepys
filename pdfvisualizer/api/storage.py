import json
import os
import tempfile
from pathlib import Path


class Storage:
    def __init__(self, base_dir: str | None = None) -> None:
        base_path = base_dir or os.environ.get("PDFVIZ_STORAGE_DIR")
        if base_path:
            self.base_dir = Path(base_path)
        else:
            self.base_dir = Path(tempfile.gettempdir()) / "pdfvisualizer"

        self.uploads_dir = self.base_dir / "uploads"
        self.parsed_dir = self.base_dir / "parsed"
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self.parsed_dir.mkdir(parents=True, exist_ok=True)

    def pdf_path(self, pdf_id: str) -> Path:
        return self.uploads_dir / f"{pdf_id}.pdf"

    def parsed_path(self, pdf_id: str) -> Path:
        return self.parsed_dir / pdf_id

    def meta_path(self, pdf_id: str) -> Path:
        return self.parsed_path(pdf_id) / "meta.json"

    def graph_path(self, pdf_id: str) -> Path:
        return self.parsed_path(pdf_id) / "graph.json"

    def pages_path(self, pdf_id: str) -> Path:
        return self.parsed_path(pdf_id) / "pages.json"

    def xref_path(self, pdf_id: str) -> Path:
        return self.parsed_path(pdf_id) / "xref.json"

    def index_path(self, pdf_id: str) -> Path:
        return self.parsed_path(pdf_id) / "index.json"

    def error_path(self, pdf_id: str) -> Path:
        return self.parsed_path(pdf_id) / "error.json"

    def write_json(self, path: Path, data: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")

    def read_json(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def remove_pdf(self, pdf_id: str) -> None:
        pdf_path = self.pdf_path(pdf_id)
        if pdf_path.exists():
            pdf_path.unlink()

        parsed_dir = self.parsed_path(pdf_id)
        if parsed_dir.exists():
            for item in parsed_dir.glob("*"):
                item.unlink()
            parsed_dir.rmdir()
