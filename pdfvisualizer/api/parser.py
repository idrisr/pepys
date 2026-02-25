from __future__ import annotations

import io
import re
import string
from collections import Counter
from dataclasses import dataclass
from typing import Any

try:
    import pikepdf
except ImportError as exc:  # pragma: no cover - dependency handled at runtime
    raise RuntimeError("pikepdf is required for PDF parsing") from exc


MAX_REFERENCE_DEPTH = 6
MAX_DICT_ITEMS = 50
MAX_LIST_ITEMS = 50
MAX_PREVIEW_BYTES = 8192


@dataclass(frozen=True)
class ObjRef:
    obj_id: str
    path: str


def format_objgen(objgen: tuple[int, int]) -> str:
    return f"{objgen[0]} {objgen[1]} R"


def parse_obj_id(value: str) -> tuple[int, int]:
    cleaned = value.strip().replace("R", "").replace("r", "")
    parts = re.split(r"[\s:_-]+", cleaned)
    if len(parts) < 2:
        raise ValueError("Object id must include object and generation numbers")
    return int(parts[0]), int(parts[1])


def _strip_name(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text[1:] if text.startswith("/") else text


def _key_name(value: Any) -> str:
    return str(value)


def _dict_get(obj: Any, key: str) -> Any | None:
    try:
        return obj.get(key)
    except Exception:
        try:
            return obj.get(pikepdf.Name(key))
        except Exception:
            return None


def _is_dictionary(value: Any) -> bool:
    return isinstance(value, pikepdf.Dictionary)


def _is_array(value: Any) -> bool:
    return isinstance(value, pikepdf.Array)


def _is_stream(value: Any) -> bool:
    return isinstance(value, pikepdf.Stream)


def _is_indirect(value: Any) -> bool:
    return isinstance(value, pikepdf.Object) and value.is_indirect


def _extract_filters(stream_dict: Any) -> list[str]:
    filters: list[str] = []
    if stream_dict is None:
        return filters

    filter_value = _dict_get(stream_dict, "/Filter")
    if filter_value is None:
        return filters

    if isinstance(filter_value, pikepdf.Array):
        for item in filter_value:
            name = _strip_name(item)
            if name:
                filters.append(name)
    else:
        name = _strip_name(filter_value)
        if name:
            filters.append(name)

    return filters


def _safe_int(value: Any) -> int | None:
    try:
        if hasattr(value, "as_int"):
            return int(value.as_int())
        return int(value)
    except Exception:
        return None


def _simplify(value: Any, depth: int) -> Any:
    if depth < 0:
        return "..."

    if _is_indirect(value):
        return format_objgen(value.objgen)

    if _is_stream(value):
        return {"__stream__": True, "dict": _simplify(value.stream_dict, depth - 1)}

    if _is_dictionary(value):
        items = list(value.items())
        out: dict[str, Any] = {}
        for idx, (key, item) in enumerate(items):
            if idx >= MAX_DICT_ITEMS:
                out["__truncated__"] = True
                break
            out[_key_name(key)] = _simplify(item, depth - 1)
        return out

    if _is_array(value):
        items: list[Any] = []
        for idx, item in enumerate(value):
            if idx >= MAX_LIST_ITEMS:
                items.append("...")
                break
            items.append(_simplify(item, depth - 1))
        return items

    if isinstance(value, pikepdf.Name):
        return str(value)

    if isinstance(value, pikepdf.String):
        return str(value)

    if isinstance(value, (int, float, bool)) or value is None:
        return value

    return str(value)


def _collect_references(
    value: Any,
    source_id: str,
    path: str,
    edges: set[tuple[str, str, str]],
    depth: int,
    root: bool = False,
) -> None:
    if depth < 0 or value is None:
        return

    if _is_indirect(value) and not root:
        target_id = format_objgen(value.objgen)
        if target_id != source_id:
            edges.add((source_id, target_id, path or "ref"))
        return

    if _is_stream(value):
        _collect_references(value.stream_dict, source_id, path, edges, depth - 1)
        return

    if _is_dictionary(value):
        for key, item in value.items():
            next_path = f"{path}/{_key_name(key)}" if path else _key_name(key)
            _collect_references(item, source_id, next_path, edges, depth - 1)
        return

    if _is_array(value):
        for idx, item in enumerate(value):
            next_path = f"{path}[{idx}]" if path else f"[{idx}]"
            _collect_references(item, source_id, next_path, edges, depth - 1)


def _list_references(value: Any, depth: int = 3) -> list[str]:
    refs: set[str] = set()

    def walk(item: Any, level: int) -> None:
        if level < 0 or item is None:
            return
        if _is_indirect(item):
            refs.add(format_objgen(item.objgen))
            return
        if _is_stream(item):
            walk(item.stream_dict, level - 1)
            return
        if _is_dictionary(item):
            for _, value in item.items():
                walk(value, level - 1)
            return
        if _is_array(item):
            for value in item:
                walk(value, level - 1)

    walk(value, depth)
    return sorted(refs)


def _object_type_info(value: Any) -> tuple[str, str | None, str, bool]:
    has_stream = _is_stream(value)
    kind = "Stream" if has_stream else "Dictionary" if _is_dictionary(value) else "Object"

    dict_obj = None
    if _is_stream(value):
        dict_obj = value.stream_dict
    elif _is_dictionary(value):
        dict_obj = value

    type_name = None
    subtype = None
    if dict_obj is not None:
        type_name = _strip_name(_dict_get(dict_obj, "/Type"))
        subtype = _strip_name(_dict_get(dict_obj, "/Subtype"))

    resolved_type = type_name or kind
    return resolved_type, subtype, kind, has_stream


def _node_label(type_name: str, subtype: str | None) -> str:
    if subtype:
        return f"{type_name}/{subtype}"
    return type_name


def _node_size(value: Any) -> int | None:
    if _is_stream(value):
        length_value = _dict_get(value.stream_dict, "/Length")
        return _safe_int(length_value)
    if _is_dictionary(value):
        return len(list(value.keys()))
    if _is_array(value):
        return len(value)
    return None


def _detect_binary(data: bytes) -> bool:
    if not data:
        return False
    if b"\x00" in data:
        return True
    printable = set(bytes(string.printable, "ascii"))
    sample = data[:2048]
    non_printable = sum(1 for b in sample if b not in printable)
    return non_printable / max(len(sample), 1) > 0.3


def _count_text_ops(data: bytes) -> int:
    if not data:
        return 0

    count = 0
    token = bytearray()
    in_string = False
    in_hex = False
    escape = False
    idx = 0

    def flush_token() -> None:
        nonlocal count
        if not token:
            return
        value = bytes(token)
        if value in (b"Tj", b"TJ", b"'", b'"'):
            count += 1
        token.clear()

    while idx < len(data):
        char = data[idx]

        if in_string:
            if escape:
                escape = False
            elif char == ord("\\"):
                escape = True
            elif char == ord(")"):
                in_string = False
            idx += 1
            continue

        if in_hex:
            if char == ord(">"):
                in_hex = False
            idx += 1
            continue

        if char == ord("("):
            flush_token()
            in_string = True
            idx += 1
            continue

        if char == ord("<"):
            flush_token()
            if idx + 1 < len(data) and data[idx + 1] == ord("<"):
                idx += 2
            else:
                in_hex = True
                idx += 1
            continue

        if char == ord(">"):
            flush_token()
            if idx + 1 < len(data) and data[idx + 1] == ord(">"):
                idx += 2
            else:
                idx += 1
            continue

        if char == ord("%"):
            flush_token()
            while idx < len(data) and data[idx] not in (ord("\n"), ord("\r")):
                idx += 1
            continue

        if char in (ord("\n"), ord("\r"), ord("\t"), ord("\f"), ord(" ")):
            flush_token()
            idx += 1
            continue

        if char in (ord("["), ord("]"), ord("{"), ord("}")):
            flush_token()
            idx += 1
            continue

        if char in (ord("'"), ord('"')):
            flush_token()
            token.append(char)
            flush_token()
            idx += 1
            continue

        token.append(char)
        idx += 1

    flush_token()
    return count


def _content_stream_entries(page_obj: Any) -> list[dict[str, Any]]:
    contents = _dict_get(page_obj, "/Contents")
    if contents is None:
        return []

    streams = contents if isinstance(contents, pikepdf.Array) else [contents]
    entries: list[dict[str, Any]] = []

    for stream in streams:
        if not _is_stream(stream):
            continue

        obj_id = format_objgen(stream.objgen) if stream.is_indirect else None
        length = _safe_int(_dict_get(stream.stream_dict, "/Length"))
        decoded = True

        try:
            data = stream.read_bytes()
        except Exception:
            decoded = False
            try:
                data = stream.read_raw_bytes()
            except Exception:
                data = b""

        text_ops = _count_text_ops(data)

        entries.append(
            {
                "id": obj_id,
                "length": length,
                "decoded": decoded,
                "text_ops": text_ops,
            }
        )

    return entries


def _page_xobjects(page_obj: Any) -> list[dict[str, Any]]:
    resources = _dict_get(page_obj, "/Resources")
    if resources is None or not _is_dictionary(resources):
        return []

    xobjects_dict = _dict_get(resources, "/XObject")
    if xobjects_dict is None or not _is_dictionary(xobjects_dict):
        return []

    xobjects: list[dict[str, Any]] = []
    for key, value in xobjects_dict.items():
        if not isinstance(value, pikepdf.Object):
            continue
        obj_id = format_objgen(value.objgen) if value.is_indirect else None
        obj_type, subtype, kind, has_stream = _object_type_info(value)
        xobjects.append(
            {
                "name": _key_name(key),
                "obj_id": obj_id,
                "type": obj_type,
                "subtype": subtype,
                "kind": kind,
                "has_stream": has_stream,
            }
        )

    return xobjects


def parse_pdf(path: str) -> dict[str, Any]:
    with pikepdf.open(path) as pdf:
        nodes: list[dict[str, Any]] = []
        edges: set[tuple[str, str, str]] = set()
        type_counts: Counter[str] = Counter()
        index: dict[str, dict[str, Any]] = {}

        for obj in pdf.objects:
            if obj is None:
                continue
            if not hasattr(obj, "objgen"):
                continue

            obj_id = format_objgen(obj.objgen)
            obj_type, subtype, kind, has_stream = _object_type_info(obj)
            label = _node_label(obj_type, subtype)
            size = _node_size(obj)

            nodes.append(
                {
                    "id": obj_id,
                    "type": obj_type,
                    "subtype": subtype,
                    "kind": kind,
                    "label": label,
                    "size": size,
                    "has_stream": has_stream,
                }
            )

            type_counts[obj_type] += 1

            keys: list[str] = []
            if _is_dictionary(obj):
                keys = [_key_name(key) for key in obj.keys()]
            elif _is_stream(obj):
                keys = [_key_name(key) for key in obj.stream_dict.keys()]

            index[obj_id] = {
                "type": obj_type,
                "subtype": subtype,
                "kind": kind,
                "keys": keys,
                "has_stream": has_stream,
                "label": label,
            }

            _collect_references(
                obj, obj_id, "", edges, depth=MAX_REFERENCE_DEPTH, root=True
            )

        edges_list = [
            {"from": source, "to": target, "via_key": via}
            for source, target, via in sorted(edges)
        ]

        degree: Counter[str] = Counter()
        for edge in edges_list:
            degree[edge["from"]] += 1
            degree[edge["to"]] += 1

        graph = {
            "nodes": nodes,
            "edges": edges_list,
            "stats": {
                "type_counts": dict(type_counts),
                "stream_count": sum(1 for node in nodes if node["has_stream"]),
                "max_degree": max(degree.values(), default=0),
            },
        }

        pages: list[dict[str, Any]] = []
        for idx, page in enumerate(pdf.pages):
            page_obj = page.obj
            page_id = format_objgen(page_obj.objgen) if page_obj.is_indirect else None
            resources = _list_references(_dict_get(page_obj, "/Resources"))
            contents = _list_references(_dict_get(page_obj, "/Contents"))
            annots = _list_references(_dict_get(page_obj, "/Annots"))
            content_streams = _content_stream_entries(page_obj)
            xobjects = _page_xobjects(page_obj)
            pages.append(
                {
                    "index": idx,
                    "page": idx + 1,
                    "obj_id": page_id,
                    "resources": resources,
                    "contents": contents,
                    "content_streams": content_streams,
                    "xobjects": xobjects,
                    "annots": annots,
                }
            )

        xref_buffer = io.StringIO()
        try:
            pdf.show_xref_table(xref_buffer)
            xref_text = xref_buffer.getvalue().splitlines()
        except Exception:
            xref_text = []

        info = {
            "page_count": len(pdf.pages),
            "object_count": len(nodes),
            "pdf_version": pdf.pdf_version,
            "is_encrypted": pdf.is_encrypted,
            "is_linearized": pdf.is_linearized,
        }

        return {
            "graph": graph,
            "pages": pages,
            "xref": {"lines": xref_text},
            "index": index,
            "info": info,
        }


def object_detail(path: str, obj_id: str) -> dict[str, Any]:
    objgen = parse_obj_id(obj_id)
    with pikepdf.open(path) as pdf:
        obj = pdf.get_object(objgen)

        obj_type, subtype, kind, has_stream = _object_type_info(obj)
        label = _node_label(obj_type, subtype)
        size = _node_size(obj)

        refs: list[ObjRef] = []
        edges: set[tuple[str, str, str]] = set()
        _collect_references(obj, format_objgen(objgen), "", edges, depth=MAX_REFERENCE_DEPTH, root=True)
        for source, target, via in sorted(edges):
            if source == format_objgen(objgen):
                refs.append(ObjRef(obj_id=target, path=via))

        detail: dict[str, Any] = {
            "id": format_objgen(objgen),
            "type": obj_type,
            "subtype": subtype,
            "kind": kind,
            "label": label,
            "size": size,
            "has_stream": has_stream,
            "dict": _simplify(obj.stream_dict if _is_stream(obj) else obj, 4)
            if (_is_dictionary(obj) or _is_stream(obj))
            else None,
            "refs": [ref.__dict__ for ref in refs],
        }

        if _is_stream(obj):
            detail["stream"] = stream_preview(obj)

        return detail


def stream_preview(obj: Any) -> dict[str, Any]:
    if not _is_stream(obj):
        return {"preview": None}

    data = b""
    decoded = True
    try:
        data = obj.read_bytes()
    except Exception:
        decoded = False
        try:
            data = obj.read_raw_bytes()
        except Exception:
            data = b""

    truncated = len(data) > MAX_PREVIEW_BYTES
    preview_bytes = data[:MAX_PREVIEW_BYTES]
    is_binary = _detect_binary(preview_bytes)

    if is_binary:
        preview = preview_bytes.hex()
        encoding = "hex"
    else:
        preview = preview_bytes.decode("utf-8", errors="replace")
        encoding = "utf-8"

    stream_dict = obj.stream_dict
    stream_length = _safe_int(_dict_get(stream_dict, "/Length"))
    filters = _extract_filters(stream_dict)

    return {
        "filters": filters,
        "length": stream_length,
        "decoded": decoded,
        "preview": preview,
        "preview_encoding": encoding,
        "truncated": truncated,
        "is_binary": is_binary,
    }
