const API_BASE = import.meta.env.VITE_API_BASE || "";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, options);
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    const message = error.error || `Request failed: ${response.status}`;
    throw new Error(message);
  }
  return response.json();
}

export async function uploadPdf(file) {
  const form = new FormData();
  form.append("file", file);
  return request("/api/pdfs", { method: "POST", body: form });
}

export async function getPdfMeta(pdfId) {
  return request(`/api/pdfs/${pdfId}`);
}

export async function getGraph(pdfId) {
  return request(`/api/pdfs/${pdfId}/graph`);
}

export async function getObjectDetail(pdfId, objId) {
  return request(`/api/pdfs/${pdfId}/object/${encodeURIComponent(objId)}`);
}

export async function searchObjects(pdfId, query) {
  return request(`/api/pdfs/${pdfId}/search?q=${encodeURIComponent(query)}`);
}

export async function getPages(pdfId) {
  return request(`/api/pdfs/${pdfId}/pages`);
}

export async function deletePdf(pdfId) {
  return request(`/api/pdfs/${pdfId}`, { method: "DELETE" });
}
