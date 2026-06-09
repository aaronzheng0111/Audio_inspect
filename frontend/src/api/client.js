import axios from "axios";

// Single axios instance for the whole app. The Vite dev server proxies /api to
// the Django backend (see vite.config.js), so a relative baseURL works in dev
// and in any same-origin deployment.
const http = axios.create({
  baseURL: "/api",
  headers: { "Content-Type": "application/json" },
  timeout: 0, // metric computation can be long; rely on the server instead.
});

// Normalise backend errors ({"error": "..."}) into thrown Error messages.
function unwrapError(error) {
  if (!error?.response) {
    const msg = error?.message || "Network error";
    if (msg.includes("Network Error") || msg.includes("timeout")) {
      return new Error(
        "Cannot reach the backend API. Stop any old servers and restart with: bash start.sh"
      );
    }
    return new Error(msg);
  }
  const status = error.response.status;
  const body = error.response.data;
  const detail = body?.error || body?.detail || error.message || "Unexpected error";
  if (status === 404 && typeof detail === "string" && !detail.includes("session")) {
    return new Error(
      `${detail} — If you see a generic 404, restart with bash start.sh ` +
        "(backend on port 9081, frontend on 9173 — run bash start.sh)."
    );
  }
  return new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
}

export const api = {
  loadDataset: (csvPath, sampleRows = 15) =>
    http
      .post("/dataset/load", { csv_path: csvPath, sample_rows: sampleRows })
      .then((r) => r.data)
      .catch((e) => Promise.reject(unwrapError(e))),

  mapAttributes: (sessionId, mapping) =>
    http
      .post("/dataset/map", { session_id: sessionId, mapping })
      .then((r) => r.data)
      .catch((e) => Promise.reject(unwrapError(e))),

  listMetrics: () =>
    http
      .get("/metrics")
      .then((r) => r.data)
      .catch((e) => Promise.reject(unwrapError(e))),

  estimate: (sessionId, metrics) =>
    http
      .post("/metrics/estimate", { session_id: sessionId, metrics })
      .then((r) => r.data)
      .catch((e) => Promise.reject(unwrapError(e))),

  compute: (sessionId, metrics) =>
    http
      .post("/metrics/compute", { session_id: sessionId, metrics })
      .then((r) => r.data)
      .catch((e) => Promise.reject(unwrapError(e))),

  summary: (sessionId) =>
    http
      .get("/analysis/summary", { params: { session_id: sessionId } })
      .then((r) => r.data)
      .catch((e) => Promise.reject(unwrapError(e))),

  plotData: (sessionId, columns, limit, strategy) =>
    http
      .get("/analysis/plot-data", {
        params: {
          session_id: sessionId,
          columns: columns.join(","),
          limit,
          strategy,
        },
      })
      .then((r) => r.data)
      .catch((e) => Promise.reject(unwrapError(e))),

  filter: (sessionId, rules) =>
    http
      .post("/analysis/filter", { session_id: sessionId, rules })
      .then((r) => r.data)
      .catch((e) => Promise.reject(unwrapError(e))),

  exportCsv: (sessionId, rules) =>
    http
      .post("/export/csv", { session_id: sessionId, rules })
      .then((r) => r.data)
      .catch((e) => Promise.reject(unwrapError(e))),

  exportReport: (sessionId, rules) =>
    http
      .post("/export/report", { session_id: sessionId, rules })
      .then((r) => r.data)
      .catch((e) => Promise.reject(unwrapError(e))),

  audioStreamUrl: (sessionId, rowIndex) =>
    `/api/audio/stream?session_id=${encodeURIComponent(sessionId)}&row_index=${rowIndex}`,
};

export default api;
