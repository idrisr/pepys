import { useEffect, useMemo, useRef, useState } from "react";
import { GlobalWorkerOptions, Util, getDocument } from "pdfjs-dist";
import workerSrc from "pdfjs-dist/build/pdf.worker.min.mjs?url";

GlobalWorkerOptions.workerSrc = workerSrc;

const MAX_TREE_DEPTH = 3;
const MAX_TREE_NODES = 160;
const MAX_CHILDREN = 30;

function buildNode({
  id,
  via,
  depth,
  visited,
  nodesById,
  edgesByFrom,
  limit,
  labelOverride,
  metaText,
}) {
  if (!id || visited.has(id) || depth < 0 || limit.count >= MAX_TREE_NODES) {
    if (limit.count >= MAX_TREE_NODES) {
      limit.reached = true;
    }
    return null;
  }

  visited.add(id);
  limit.count += 1;

  const node = nodesById.get(id);
  const label = labelOverride || node?.label || node?.type || id;
  const children = [];

  if (depth > 0) {
    const edges = edgesByFrom.get(id) || [];
    for (const edge of edges.slice(0, MAX_CHILDREN)) {
      const child = buildNode({
        id: edge.to,
        via: edge.via_key,
        depth: depth - 1,
        visited,
        nodesById,
        edgesByFrom,
        limit,
      });
      if (child) {
        children.push(child);
      }
    }
  }

  return {
    id,
    label,
    type: node?.type || "Object",
    subtype: node?.subtype || null,
    via,
    metaText,
    children,
  };
}

function TreeNode({ node, depth, onSelect, selectedId }) {
  const isSelected = selectedId === node.id;
  return (
    <div className="tree-node" style={{ paddingLeft: depth * 14 }}>
      <button
        className={`tree-node-button ${isSelected ? "active" : ""}`}
        type="button"
        onClick={() => onSelect(node.id)}
      >
        <span className="tree-label">{node.label}</span>
        <span className="tree-id">{node.id}</span>
        {node.metaText && <span className="tree-meta">{node.metaText}</span>}
        {node.via && <span className="tree-via">via {node.via}</span>}
      </button>
      {node.children?.length > 0 && (
        <div className="tree-children">
          {node.children.map((child) => (
            <TreeNode
              key={`${node.id}-${child.id}`}
              node={child}
              depth={depth + 1}
              onSelect={onSelect}
              selectedId={selectedId}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default function PageReader({
  pdfId,
  pages,
  graph,
  selectedObjectId,
  onSelectObject,
}) {
  const containerRef = useRef(null);
  const canvasRef = useRef(null);
  const renderTaskRef = useRef(null);
  const [doc, setDoc] = useState(null);
  const [pageIndex, setPageIndex] = useState(0);
  const [pageCount, setPageCount] = useState(0);
  const [containerWidth, setContainerWidth] = useState(0);
  const [rendering, setRendering] = useState(false);
  const [error, setError] = useState(null);
  const [canvasSize, setCanvasSize] = useState({ width: 0, height: 0 });
  const [textItems, setTextItems] = useState([]);
  const safeSelect = onSelectObject || (() => {});

  const currentPage = pages?.[pageIndex] || null;

  useEffect(() => {
    if (!pdfId) {
      setDoc(null);
      setPageCount(0);
      setPageIndex(0);
      setTextItems([]);
      setCanvasSize({ width: 0, height: 0 });
      return;
    }

    setError(null);
    const loadingTask = getDocument({ url: `/api/pdfs/${pdfId}/file` });
    loadingTask.promise
      .then((loadedDoc) => {
        setDoc(loadedDoc);
        setPageCount(loadedDoc.numPages || 0);
        setPageIndex(0);
      })
      .catch((err) => {
        setError(err.message || "Failed to load PDF");
      });

    return () => {
      loadingTask.destroy();
    };
  }, [pdfId]);

  useEffect(() => {
    const element = containerRef.current;
    if (!element) {
      return undefined;
    }

    const observer = new ResizeObserver((entries) => {
      if (!entries.length) {
        return;
      }
      setContainerWidth(entries[0].contentRect.width || 0);
    });

    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!doc || !canvasRef.current || !containerWidth) {
      return;
    }

    setRendering(true);
    setTextItems([]);
    const pageNumber = Math.min(pageIndex + 1, pageCount || pageIndex + 1);
    let cancelled = false;

    doc.getPage(pageNumber)
      .then((page) => {
        const baseViewport = page.getViewport({ scale: 1 });
        const availableWidth = Math.max(containerWidth - 24, 300);
        const nextScale = Math.min(2.2, Math.max(0.6, availableWidth / baseViewport.width));
        const viewport = page.getViewport({ scale: nextScale });

        const canvas = canvasRef.current;
        const context = canvas.getContext("2d");
        if (!context) {
          return null;
        }

        canvas.width = viewport.width;
        canvas.height = viewport.height;
        setCanvasSize({ width: viewport.width, height: viewport.height });

        if (renderTaskRef.current) {
          renderTaskRef.current.cancel();
        }

        renderTaskRef.current = page.render({ canvasContext: context, viewport });
        const renderPromise = renderTaskRef.current.promise;
        const textPromise = page
          .getTextContent()
          .then((textContent) => {
            if (cancelled) {
              return [];
            }
            const items = textContent.items
              .filter((item) => item.str && item.str.trim())
              .map((item, index) => {
                const transform = Util.transform(viewport.transform, item.transform);
                const x = transform[4];
                const y = transform[5];
                const width = Math.abs(item.width * viewport.scale);
                const height = Math.abs(item.height * viewport.scale);
                return {
                  id: index,
                  x,
                  y: y - height,
                  width,
                  height,
                  text: item.str,
                };
              });
            return items;
          })
          .catch(() => []);

        return Promise.all([renderPromise, textPromise]);
      })
      .then((result) => {
        if (cancelled) {
          return;
        }
        if (Array.isArray(result)) {
          const textData = result[1];
          if (Array.isArray(textData)) {
            setTextItems(textData);
          }
        }
        setRendering(false);
      })
      .catch((err) => {
        if (err?.name !== "RenderingCancelledException") {
          setError(err.message || "Failed to render page");
        }
        setRendering(false);
      });

    return () => {
      cancelled = true;
      if (renderTaskRef.current) {
        renderTaskRef.current.cancel();
      }
    };
  }, [doc, pageIndex, pageCount, containerWidth]);

  const treeData = useMemo(() => {
    if (!currentPage) {
      return { sections: [], truncated: false };
    }

    const nodesById = new Map((graph?.nodes || []).map((node) => [node.id, node]));
    const edgesByFrom = new Map();
    (graph?.edges || []).forEach((edge) => {
      if (!edgesByFrom.has(edge.from)) {
        edgesByFrom.set(edge.from, []);
      }
      edgesByFrom.get(edge.from).push(edge);
    });

    const limit = { count: 0, reached: false };

    const buildSection = (title, entries) => {
      const visited = new Set();
      const nodes = [];
      for (const entry of entries || []) {
        if (!entry?.id) {
          continue;
        }
        const node = buildNode({
          id: entry.id,
          via: null,
          depth: MAX_TREE_DEPTH,
          visited,
          nodesById,
          edgesByFrom,
          limit,
          labelOverride: entry.label,
          metaText: entry.metaText,
        });
        if (node) {
          nodes.push(node);
        }
      }
      return { title, nodes };
    };

    const contentEntries = (currentPage.content_streams || []).length
      ? (currentPage.content_streams || [])
          .filter((stream) => stream?.id)
          .map((stream) => ({
            id: stream.id,
            label: `Stream ${stream.id}`,
            metaText: stream.text_ops ? `${stream.text_ops} text ops` : "no text ops",
          }))
      : (currentPage.contents || []).map((id) => ({
          id,
          label: `Stream ${id}`,
          metaText: "text ops unavailable",
        }));

    const xobjectEntries = (currentPage.xobjects || [])
      .filter((item) => item?.obj_id)
      .map((item) => ({
        id: item.obj_id,
        label: `${item.name} · ${item.subtype || item.type || "XObject"}`,
        metaText: item.obj_id,
      }));

    const resourceEntries = (currentPage.resources || []).map((id) => ({ id }));
    const annotEntries = (currentPage.annots || []).map((id) => ({ id }));

    const sections = [
      buildSection("Content Streams", contentEntries),
      buildSection("XObjects", xobjectEntries),
      buildSection("Resources", resourceEntries),
      buildSection("Annotations", annotEntries),
    ].filter((section) => section.nodes.length > 0);

    return {
      sections,
      truncated: limit.reached,
    };
  }, [currentPage, graph]);

  const streamTextMap = useMemo(() => {
    const map = new Map();
    const streams = currentPage?.content_streams || [];
    if (!streams.length || !textItems.length) {
      return map;
    }

    const totalOps = streams.reduce((sum, stream) => sum + (stream.text_ops || 0), 0);
    let cursor = 0;
    let remainingItems = textItems.length;
    let remainingOps = totalOps;

    streams.forEach((stream, index) => {
      if (!stream.id) {
        return;
      }
      let count = 0;
      if (totalOps > 0) {
        const ops = stream.text_ops || 0;
        if (index === streams.length - 1) {
          count = remainingItems;
        } else if (remainingOps > 0) {
          count = Math.round((ops / remainingOps) * remainingItems);
        }
      } else if (index === 0) {
        count = remainingItems;
      }

      const slice = textItems.slice(cursor, cursor + count);
      map.set(stream.id, slice);
      cursor += count;
      remainingItems = Math.max(0, remainingItems - count);
      remainingOps = Math.max(0, remainingOps - (stream.text_ops || 0));
    });

    return map;
  }, [currentPage, textItems]);

  const selectedStream = useMemo(() => {
    if (!selectedObjectId || !currentPage?.content_streams) {
      return null;
    }
    return currentPage.content_streams.find((stream) => stream.id === selectedObjectId) || null;
  }, [selectedObjectId, currentPage]);

  const selectedNode = useMemo(() => {
    if (!selectedObjectId || !graph?.nodes?.length) {
      return null;
    }
    return graph.nodes.find((node) => node.id === selectedObjectId) || null;
  }, [selectedObjectId, graph]);

  const activeBoxes = selectedStream ? streamTextMap.get(selectedStream.id) || [] : [];

  const streamHint = useMemo(() => {
    if (!selectedObjectId) {
      return "Select a content stream to see estimated text coverage.";
    }
    if (selectedStream) {
      if (activeBoxes.length === 0) {
        return `No text items mapped for ${selectedStream.id}.`;
      }
      return `Highlighting estimated text from ${selectedStream.id}.`;
    }
    if (selectedNode?.has_stream) {
      return "Selected stream is not part of this page's /Contents.";
    }
    return "";
  }, [selectedObjectId, selectedStream, activeBoxes.length, selectedNode]);

  if (!pdfId) {
    return (
      <div className="reader-panel">
        <div className="reader-empty">
          <h2>Page Reader</h2>
          <p className="muted">Upload a PDF to read it page by page.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="reader-panel">
      <div className="reader-header">
        <div>
          <h2>Page Reader</h2>
          <p className="muted">Render the PDF page and inspect the object tree.</p>
        </div>
        <div className="page-controls">
          <button
            className="ghost"
            type="button"
            disabled={pageIndex <= 0}
            onClick={() => setPageIndex((prev) => Math.max(prev - 1, 0))}
          >
            Prev
          </button>
          <div className="page-input">
            <input
              type="number"
              min="1"
              max={pageCount || 1}
              value={pageCount ? pageIndex + 1 : 0}
              onChange={(event) => {
                const next = Number(event.target.value);
                if (Number.isNaN(next)) {
                  return;
                }
                const clamped = Math.min(Math.max(next, 1), pageCount || 1);
                setPageIndex(clamped - 1);
              }}
            />
            <span className="muted">/ {pageCount || "-"}</span>
          </div>
          <button
            className="ghost"
            type="button"
            disabled={pageCount ? pageIndex >= pageCount - 1 : true}
            onClick={() => setPageIndex((prev) => Math.min(prev + 1, pageCount - 1))}
          >
            Next
          </button>
        </div>
      </div>

      <div className="reader-grid">
        <div className="page-canvas" ref={containerRef}>
          {error && <div className="error-banner">{error}</div>}
          <div
            className="canvas-stack"
            style={{
              width: canvasSize.width || "auto",
              height: canvasSize.height || "auto",
            }}
          >
            <canvas ref={canvasRef} />
            {activeBoxes.length > 0 && (
              <div className="text-overlay">
                {activeBoxes.map((box) => (
                  <div
                    key={box.id}
                    className="text-box"
                    style={{
                      left: box.x,
                      top: box.y,
                      width: box.width,
                      height: box.height,
                    }}
                  />
                ))}
              </div>
            )}
          </div>
          {rendering && <div className="rendering-pill">Rendering...</div>}
          {streamHint && <div className="stream-pill">{streamHint}</div>}
        </div>

        <div className="page-tree">
          <div className="tree-header">
            <div>
              <h3>Page Map</h3>
              <p className="muted">
                Page {pageIndex + 1} {currentPage?.obj_id ? `· ${currentPage.obj_id}` : ""}
              </p>
              <p className="muted small">
                Click a content stream to highlight estimated text coverage.
              </p>
            </div>
            {treeData.truncated && (
              <span className="tree-warning">Tree truncated</span>
            )}
          </div>

          {treeData.sections.length === 0 && (
            <p className="muted">No object mapping available.</p>
          )}

          {treeData.sections.map((section) => (
            <div className="tree-section" key={section.title}>
              <h4>{section.title}</h4>
              <div className="tree-branch">
              {section.nodes.map((node) => (
                  <TreeNode
                    key={`${section.title}-${node.id}`}
                    node={node}
                    depth={0}
                    onSelect={safeSelect}
                    selectedId={selectedObjectId}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
