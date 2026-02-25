import mimetypes
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, request, send_file, send_from_directory
from werkzeug.utils import secure_filename

from parser import object_detail, parse_pdf
from storage import Storage


def _max_upload_bytes() -> int:
    max_mb = os.environ.get("PDFVIZ_MAX_MB", "100")
    try:
        return int(max_mb) * 1024 * 1024
    except ValueError:
        return 100 * 1024 * 1024


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_obj_id(value: str) -> str:
    cleaned = value.strip()
    if cleaned.lower().endswith(" r"):
        return cleaned
    if cleaned.lower().endswith("r"):
        cleaned = cleaned[:-1].strip()
    parts = [part for part in cleaned.replace("_", " ").replace("-", " ").split() if part]
    if len(parts) >= 2:
        return f"{parts[0]} {parts[1]} R"
    return value


def _int_arg(name: str, default: int = 0) -> int:
    raw = request.args.get(name, "")
    if raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def create_app() -> Flask:
    mimetypes.add_type("application/javascript", ".mjs")
    static_dir_env = os.environ.get("PDFVIZ_WEB_DIST")
    static_dir = Path(static_dir_env).resolve() if static_dir_env else None

    if static_dir:
        app = Flask(
            __name__,
            static_folder=str(static_dir),
            static_url_path="",
        )
    else:
        app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = _max_upload_bytes()

    storage = Storage()

    @app.before_request
    def _handle_options() -> tuple[str, int] | None:
        if request.method == "OPTIONS":
            return "", 204
        return None

    @app.after_request
    def _apply_cors(response):
        origin = os.environ.get("PDFVIZ_CORS_ORIGIN", "*")
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Methods"] = "GET,POST,DELETE,OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        return response

    @app.route("/api/health", methods=["GET"])
    def health() -> tuple[dict, int]:
        return {"status": "ok"}, 200

    @app.route("/api/pdfs", methods=["POST"])
    def upload_pdf():
        if "file" not in request.files:
            return {"error": "Missing file"}, 400

        upload = request.files["file"]
        if not upload or not upload.filename:
            return {"error": "Missing filename"}, 400

        pdf_id = uuid.uuid4().hex
        filename = secure_filename(upload.filename) or f"{pdf_id}.pdf"
        pdf_path = storage.pdf_path(pdf_id)
        upload.save(pdf_path)

        try:
            parsed = parse_pdf(str(pdf_path))
        except Exception as exc:
            storage.write_json(storage.error_path(pdf_id), {"error": str(exc)})
            return {"error": "Failed to parse PDF", "detail": str(exc)}, 500

        info = parsed["info"]
        meta = {
            "id": pdf_id,
            "filename": filename,
            "size": Path(pdf_path).stat().st_size,
            "created_at": _now_iso(),
            **info,
        }

        storage.write_json(storage.meta_path(pdf_id), meta)
        storage.write_json(storage.graph_path(pdf_id), parsed["graph"])
        storage.write_json(storage.pages_path(pdf_id), {"pages": parsed["pages"]})
        storage.write_json(storage.xref_path(pdf_id), parsed["xref"])
        storage.write_json(storage.index_path(pdf_id), {"index": parsed["index"]})

        return {"id": pdf_id, "meta": meta}, 200

    @app.route("/api/pdfs/<pdf_id>", methods=["GET"])
    def get_meta(pdf_id: str):
        meta_path = storage.meta_path(pdf_id)
        if not meta_path.exists():
            return {"error": "Not found"}, 404
        return storage.read_json(meta_path), 200

    @app.route("/api/pdfs/<pdf_id>/status", methods=["GET"])
    def get_status(pdf_id: str):
        error_path = storage.error_path(pdf_id)
        if error_path.exists():
            error = storage.read_json(error_path)
            return {"status": "error", **error}, 200

        meta_path = storage.meta_path(pdf_id)
        graph_path = storage.graph_path(pdf_id)
        if meta_path.exists() and graph_path.exists():
            return {"status": "done"}, 200

        return {"status": "missing"}, 404

    @app.route("/api/pdfs/<pdf_id>/graph", methods=["GET"])
    def get_graph(pdf_id: str):
        graph_path = storage.graph_path(pdf_id)
        if not graph_path.exists():
            return {"error": "Not found"}, 404

        graph = storage.read_json(graph_path)
        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])

        type_filter = request.args.get("type", "").strip()
        if type_filter:
            filtered = []
            type_filter_lower = type_filter.lower()
            for node in nodes:
                node_type = (node.get("type") or "").lower()
                node_subtype = (node.get("subtype") or "").lower()
                if node_type == type_filter_lower or node_subtype == type_filter_lower:
                    filtered.append(node)
            nodes = filtered

        total_nodes = len(nodes)
        offset = _int_arg("offset", 0)
        limit = _int_arg("limit", 0)
        if offset or limit:
            nodes = nodes[offset : offset + limit] if limit else nodes[offset:]

        allowed = {node["id"] for node in nodes}
        edges = [edge for edge in edges if edge["from"] in allowed and edge["to"] in allowed]

        response = {
            "nodes": nodes,
            "edges": edges,
            "stats": graph.get("stats", {}),
            "total_nodes": total_nodes,
            "total_edges": len(edges),
            "truncated": len(nodes) < total_nodes,
        }
        return jsonify(response)

    @app.route("/api/pdfs/<pdf_id>/object/<path:obj_id>", methods=["GET"])
    def get_object(pdf_id: str, obj_id: str):
        pdf_path = storage.pdf_path(pdf_id)
        if not pdf_path.exists():
            return {"error": "Not found"}, 404

        normalized = _normalize_obj_id(obj_id)
        try:
            detail = object_detail(str(pdf_path), normalized)
        except Exception as exc:
            return {"error": "Failed to load object", "detail": str(exc)}, 400

        return jsonify(detail)

    @app.route("/api/pdfs/<pdf_id>/object/<path:obj_id>/stream", methods=["GET"])
    def get_object_stream(pdf_id: str, obj_id: str):
        pdf_path = storage.pdf_path(pdf_id)
        if not pdf_path.exists():
            return {"error": "Not found"}, 404

        normalized = _normalize_obj_id(obj_id)
        try:
            detail = object_detail(str(pdf_path), normalized)
        except Exception as exc:
            return {"error": "Failed to load object", "detail": str(exc)}, 400

        stream = detail.get("stream")
        if not stream:
            return {"error": "Object has no stream"}, 404
        return jsonify({"id": detail["id"], **stream})

    @app.route("/api/pdfs/<pdf_id>/file", methods=["GET"])
    def get_pdf_file(pdf_id: str):
        pdf_path = storage.pdf_path(pdf_id)
        if not pdf_path.exists():
            return {"error": "Not found"}, 404
        return send_file(
            pdf_path,
            mimetype="application/pdf",
            as_attachment=False,
            download_name=pdf_path.name,
        )

    @app.route("/api/pdfs/<pdf_id>/xref", methods=["GET"])
    def get_xref(pdf_id: str):
        xref_path = storage.xref_path(pdf_id)
        if not xref_path.exists():
            return {"error": "Not found"}, 404
        return storage.read_json(xref_path), 200

    @app.route("/api/pdfs/<pdf_id>/pages", methods=["GET"])
    def get_pages(pdf_id: str):
        pages_path = storage.pages_path(pdf_id)
        if not pages_path.exists():
            return {"error": "Not found"}, 404
        return storage.read_json(pages_path), 200

    @app.route("/api/pdfs/<pdf_id>/search", methods=["GET"])
    def search(pdf_id: str):
        query = request.args.get("q", "").strip()
        if not query:
            return {"results": [], "count": 0}, 200

        index_path = storage.index_path(pdf_id)
        graph_path = storage.graph_path(pdf_id)
        if not index_path.exists() or not graph_path.exists():
            return {"error": "Not found"}, 404

        index = storage.read_json(index_path).get("index", {})
        nodes = storage.read_json(graph_path).get("nodes", [])
        nodes_by_id = {node["id"]: node for node in nodes}

        query_lower = query.lower()
        results: list[dict] = []
        for obj_id, entry in index.items():
            if query_lower in obj_id.lower():
                results.append(nodes_by_id.get(obj_id, {"id": obj_id}))
                continue

            fields = [
                entry.get("type") or "",
                entry.get("subtype") or "",
                entry.get("kind") or "",
                entry.get("label") or "",
            ]
            if any(query_lower in field.lower() for field in fields):
                results.append(nodes_by_id.get(obj_id, {"id": obj_id}))
                continue

            keys = entry.get("keys") or []
            if any(query_lower in key.lower() for key in keys):
                results.append(nodes_by_id.get(obj_id, {"id": obj_id}))

        results = results[:200]
        return {"results": results, "count": len(results)}, 200

    @app.route("/api/pdfs/<pdf_id>", methods=["DELETE"])
    def delete_pdf(pdf_id: str):
        storage.remove_pdf(pdf_id)
        return {"status": "deleted"}, 200

    if static_dir:
        @app.route("/")
        def ui_index():
            index_path = static_dir / "index.html"
            if index_path.exists():
                return send_from_directory(static_dir, "index.html")
            return {"error": "UI not built"}, 404

        @app.route("/<path:path>")
        def ui_assets(path: str):
            if path.startswith("api/"):
                return {"error": "Not found"}, 404

            file_path = static_dir / path
            if file_path.exists():
                return send_from_directory(static_dir, path)

            index_path = static_dir / "index.html"
            if index_path.exists():
                return send_from_directory(static_dir, "index.html")

            return {"error": "UI not built"}, 404

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PDFVIZ_PORT", "8001"))
    app.run(host="0.0.0.0", port=port, debug=True)
