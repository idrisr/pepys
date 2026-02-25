import { useEffect, useMemo, useRef } from "react";
import cytoscape from "cytoscape";
import dagre from "cytoscape-dagre";

cytoscape.use(dagre);

const TYPE_COLORS = {
  Catalog: "#0f766e",
  Page: "#2563eb",
  Pages: "#1d4ed8",
  XObject: "#b45309",
  Font: "#15803d",
  Annot: "#be123c",
  Stream: "#0f766e",
  Dictionary: "#0f172a",
};

const DEFAULT_COLOR = "#334155";

const layoutOptions = (layout) => {
  if (layout === "dagre") {
    return { name: "dagre", rankDir: "LR", spacingFactor: 1.4 };
  }
  if (layout === "concentric") {
    return { name: "concentric", minNodeSpacing: 20, levelWidth: () => 2 };
  }
  return { name: "cose", animate: true, padding: 10 };
};

export default function GraphView({
  nodes,
  edges,
  selectedId,
  highlightIds,
  onSelect,
  layout,
  focusMode,
  recenterKey,
}) {
  const containerRef = useRef(null);
  const cyRef = useRef(null);
  const onSelectRef = useRef(onSelect);

  useEffect(() => {
    onSelectRef.current = onSelect;
  }, [onSelect]);

  const elements = useMemo(() => {
    const nodeElements = nodes.map((node) => {
      const typeColor = TYPE_COLORS[node.type] || DEFAULT_COLOR;
      const size = typeof node.size === "number" ? Math.min(node.size, 8000) : 20;
      return {
        data: {
          id: node.id,
          label: node.label || node.id,
          weight: size,
          color: typeColor,
        },
      };
    });

    const edgeElements = edges.map((edge, index) => ({
      data: {
        id: `${edge.from}-${edge.to}-${index}`,
        source: edge.from,
        target: edge.to,
        label: edge.via_key || "",
      },
    }));

    return [...nodeElements, ...edgeElements];
  }, [nodes, edges]);

  useEffect(() => {
    if (!containerRef.current) {
      return undefined;
    }

    if (!cyRef.current) {
      cyRef.current = cytoscape({
        container: containerRef.current,
        elements,
        style: [
          {
            selector: "node",
            style: {
              "background-color": "data(color)",
              label: "data(label)",
              "font-family": "var(--font-display)",
              "font-size": 10,
              color: "#0f172a",
              width: "mapData(weight, 0, 8000, 26, 64)",
              height: "mapData(weight, 0, 8000, 26, 64)",
              "text-wrap": "wrap",
              "text-max-width": 90,
              "border-color": "#0f172a",
              "border-width": 1,
            },
          },
          {
            selector: "edge",
            style: {
              width: 1,
              "line-color": "#94a3b8",
              "target-arrow-color": "#94a3b8",
              "target-arrow-shape": "triangle",
              "curve-style": "bezier",
            },
          },
          {
            selector: ".selected",
            style: {
              "border-width": 3,
              "border-color": "#f97316",
            },
          },
          {
            selector: ".highlight",
            style: {
              "border-width": 3,
              "border-color": "#0ea5e9",
              "background-color": "#38bdf8",
            },
          },
          {
            selector: ".faded",
            style: {
              opacity: 0.15,
            },
          },
        ],
        layout: layoutOptions(layout),
      });

      cyRef.current.on("tap", "node", (event) => {
        onSelectRef.current(event.target.id());
      });

      cyRef.current.on("tap", (event) => {
        if (event.target === cyRef.current) {
          onSelectRef.current(null);
        }
      });
    } else {
      cyRef.current.json({ elements });
      cyRef.current.layout(layoutOptions(layout)).run();
    }

    return () => {};
  }, [elements, layout]);

  useEffect(() => {
    return () => {
      if (cyRef.current) {
        cyRef.current.destroy();
        cyRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) {
      return;
    }

    cy.elements().removeClass("selected highlight faded");

    if (Array.isArray(highlightIds)) {
      highlightIds.forEach((id) => {
        const node = cy.getElementById(id);
        if (node) {
          node.addClass("highlight");
        }
      });
    }

    if (selectedId) {
      const selected = cy.getElementById(selectedId);
      if (selected) {
        selected.addClass("selected");
        if (focusMode) {
          const neighborhood = selected.closedNeighborhood();
          cy.elements().addClass("faded");
          neighborhood.removeClass("faded");
        }
        cy.animate({ center: { eles: selected }, duration: 200 });
      }
    }
  }, [selectedId, highlightIds, focusMode]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy || cy.elements().length === 0) {
      return;
    }

    if (focusMode && selectedId) {
      const selected = cy.getElementById(selectedId);
      if (selected) {
        const neighborhood = selected.closedNeighborhood();
        cy.animate({ fit: { eles: neighborhood, padding: 40 }, duration: 200 });
        return;
      }
    }

    cy.animate({ fit: { padding: 40 }, duration: 200 });
  }, [recenterKey, focusMode, selectedId]);

  return <div className="graph-surface" ref={containerRef} />;
}
