import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Divider,
  FormControl,
  Grid,
  InputLabel,
  LinearProgress,
  MenuItem,
  Paper,
  Select,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import RestartAltIcon from "@mui/icons-material/RestartAlt";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import DownloadIcon from "@mui/icons-material/Download";
import PictureAsPdfIcon from "@mui/icons-material/PictureAsPdf";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import QueueIcon from "@mui/icons-material/Queue";
import PlotCard from "../components/PlotCard.jsx";
import FilterSlider from "../components/FilterSlider.jsx";
import StatTable from "../components/StatTable.jsx";
import api from "../api/client.js";
import { useWizard } from "../context/WizardContext.jsx";

// Step 5 (Task 5): per-attribute charts, sampling controls, threshold filters
// with before/after counts, full-dataset summary, and exports.
export default function AnalysisPage() {
  const navigate = useNavigate();
  const { sessionId, selectedMetrics, computeResult, setActiveStep, reset } =
    useWizard();

  const [summary, setSummary] = useState([]);
  const [summaryLoading, setSummaryLoading] = useState(true);
  const [plot, setPlot] = useState(null);
  const [limit, setLimit] = useState(200);
  const [strategy, setStrategy] = useState("first");
  const [rules, setRules] = useState({}); // column -> {column,min,max}
  const [appliedRules, setAppliedRules] = useState([]);
  const [filterResult, setFilterResult] = useState(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [reportPreview, setReportPreview] = useState(null);
  const [exportQueue, setExportQueue] = useState(null);
  const [computeQueuedResult, setComputeQueuedResult] = useState(null);

  // Only chart the metrics the user computed (fall back to all numeric columns).
  const metricColumns = useMemo(
    () => (selectedMetrics.length ? selectedMetrics : summary.map((s) => s.column)),
    [selectedMetrics, summary]
  );

  const boundsFor = useCallback(
    (column) => {
      const row = summary.find((s) => s.column === column);
      if (row?.min == null || row?.max == null) return null;
      return { min: row.min, max: row.max };
    },
    [summary]
  );

  const loadSummary = useCallback(async () => {
    setSummaryLoading(true);
    try {
      const res = await api.summary(sessionId);
      setSummary(res.summary);
    } finally {
      setSummaryLoading(false);
    }
  }, [sessionId]);

  const loadPlot = useCallback(async () => {
    if (metricColumns.length === 0) return;
    const res = await api.plotData(
      sessionId,
      metricColumns,
      limit,
      strategy,
      appliedRules
    );
    setPlot(res);
  }, [sessionId, metricColumns, limit, strategy, appliedRules]);

  useEffect(() => {
    setActiveStep(4);
    if (!sessionId || !computeResult) {
      navigate("/");
      return;
    }
    loadSummary().catch((e) => setError(e.message));
  }, [sessionId, computeResult, navigate, setActiveStep, loadSummary]);

  useEffect(() => {
    loadPlot().catch((e) => setError(e.message));
  }, [loadPlot]);

  // Default slider positions to the full-dataset min/max once summary loads.
  useEffect(() => {
    if (!summary.length) return;
    setRules((prev) => {
      const next = { ...prev };
      let changed = false;
      for (const col of metricColumns) {
        const row = summary.find((s) => s.column === col);
        if (!row || row.min == null || row.max == null || prev[col]) continue;
        next[col] = { column: col, min: row.min, max: row.max };
        changed = true;
      }
      return changed ? next : prev;
    });
  }, [summary, metricColumns]);

  const ruleList = () =>
    Object.values(rules).filter(
      (r) => r && (r.min !== undefined || r.max !== undefined)
    );

  const handleFilter = async () => {
    setError("");
    try {
      const activeRules = ruleList();
      const res = await api.filter(sessionId, activeRules);
      setFilterResult(res);
      setAppliedRules(activeRules);
    } catch (e) {
      setError(e.message);
    }
  };

  const handleClearFilter = () => {
    setAppliedRules([]);
    setFilterResult(null);
  };

  const handleQueueExport = async () => {
    setError("");
    try {
      const activeRules = ruleList();
      const res = await api.queueExport(sessionId, activeRules);
      setExportQueue(res);
      setComputeQueuedResult(null);
    } catch (e) {
      setError(e.message);
    }
  };

  const handleComputeQueued = async () => {
    setError("");
    setMessage("");
    setBusy(true);
    try {
      const res = await api.computeQueued(sessionId);
      setComputeQueuedResult(res);
      setExportQueue(res);
      await loadSummary();
      await loadPlot();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const handleFinalizeExport = async () => {
    setError("");
    setMessage("");
    setBusy(true);
    try {
      const activeRules = ruleList();
      const res = await api.finalizeExport(sessionId, activeRules);
      setExportQueue(res);
      setComputeQueuedResult(res);
      setMessage(
        `Filtered CSV written (${res.rows} rows, computed ${res.computed_rows ?? 0} remaining): ${res.path}`
      );
      await loadSummary();
      await loadPlot();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const handleExportCsv = async () => {
    setError("");
    setMessage("");
    setBusy(true);
    try {
      const res = await api.exportCsv(sessionId, ruleList());
      setMessage(`Filtered CSV written (${res.rows} rows): ${res.path}`);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const handleExportReport = async () => {
    setError("");
    setMessage("");
    setReportPreview(null);
    setBusy(true);
    try {
      const res = await api.exportReport(sessionId, ruleList());
      setMessage(
        `PDF report ready (before ${res.before} / after ${res.after}). Saved to: ${res.path}`
      );
      setReportPreview({
        url: api.reportPreviewUrl(sessionId),
        before: res.before,
        after: res.after,
      });
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const goBack = () => {
    setActiveStep(3);
    navigate("/metrics");
  };

  const startOver = () => {
    reset();
    navigate("/");
  };

  if (!computeResult) return null;

  return (
    <Stack spacing={3}>
      <Stack
        direction={{ xs: "column", sm: "row" }}
        justifyContent="space-between"
        alignItems={{ sm: "center" }}
        spacing={1}
      >
        <Box>
          <Typography variant="h5">Analyse & filter</Typography>
          <Typography variant="body2" color="text.secondary">
            {computeResult.n_rows} rows · metrics:{" "}
            {computeResult.computed_metrics.join(", ")}
            {computeResult.compute_rows != null &&
            computeResult.compute_rows < computeResult.n_rows
              ? ` · computed this run: ${computeResult.compute_rows.toLocaleString()}`
              : ""}
            {computeResult.approximate?.length
              ? ` · approx: ${computeResult.approximate.join(", ")}`
              : ""}
          </Typography>
        </Box>
        <Stack direction="row" spacing={1}>
          <Button startIcon={<ArrowBackIcon />} onClick={goBack}>
            Back
          </Button>
          <Button startIcon={<RestartAltIcon />} onClick={startOver}>
            Start over
          </Button>
        </Stack>
      </Stack>

      {computeResult.warning && (
        <Alert severity="warning">
          {computeResult.warning}
          {computeResult.example_resolved_path && (
            <>
              <br />
              <Typography component="span" variant="caption" sx={{ fontFamily: "'Roboto Mono', monospace" }}>
                Example path: {computeResult.example_resolved_path}
              </Typography>
            </>
          )}
        </Alert>
      )}

      {/* Sampling controls (Task 5: choose how many points to render) */}
      <Paper sx={{ p: 2, borderRadius: 3 }}>
        <Stack direction={{ xs: "column", sm: "row" }} spacing={2} alignItems="center">
          <Typography variant="subtitle2">Rendering</Typography>
          <FormControl size="small" sx={{ minWidth: 140 }}>
            <InputLabel>Sample size</InputLabel>
            <Select
              label="Sample size"
              value={limit}
              onChange={(e) => setLimit(Number(e.target.value))}
            >
              {[100, 200, 500, 1000, 2000].map((n) => (
                <MenuItem key={n} value={n}>
                  {n} points
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <FormControl size="small" sx={{ minWidth: 160 }}>
            <InputLabel>Strategy</InputLabel>
            <Select
              label="Strategy"
              value={strategy}
              onChange={(e) => setStrategy(e.target.value)}
            >
              <MenuItem value="first">First N rows</MenuItem>
              <MenuItem value="random">Random sample</MenuItem>
            </Select>
          </FormControl>
          {plot && (
            <Chip
              label={
                appliedRules.length
                  ? `showing ${plot.returned_rows} of ${plot.total_rows} filtered`
                  : `showing ${plot.returned_rows} of ${plot.total_rows}`
              }
              variant="outlined"
            />
          )}
        </Stack>
      </Paper>

      {error && <Alert severity="error">{error}</Alert>}

      {/* One card per attribute (Task 5) */}
      <Grid container spacing={2}>
        {metricColumns.map((col, i) => (
          <Grid item xs={12} md={6} key={col}>
            <PlotCard
              column={col}
              index={i}
              values={plot?.data?.[col] || []}
              sessionId={sessionId}
              rowIndices={plot?.row_indices || []}
              rows={plot?.rows || []}
              metadataColumns={plot?.metadata_columns || []}
            />
          </Grid>
        ))}
      </Grid>

      {/* Threshold filtering with before/after (Task 5) */}
      <Paper sx={{ p: 3, borderRadius: 3 }}>
        <Typography variant="h6" gutterBottom>
          Filter rules
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Slider ranges use the full-dataset min/max from the statistics summary.
          Changing sample size only affects the charts above; apply filter to
          update charts and see how many rows remain.
        </Typography>
        {summaryLoading && (
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Loading statistics for filter bounds…
          </Typography>
        )}
        <Grid container spacing={2}>
          {metricColumns.map((col) => {
            const bounds = boundsFor(col);
            return (
              <Grid item xs={12} sm={6} md={4} key={col}>
                <Card variant="outlined">
                  {bounds ? (
                    <FilterSlider
                      column={col}
                      bounds={bounds}
                      value={rules[col]}
                      onChange={(r) => setRules({ ...rules, [col]: r })}
                    />
                  ) : (
                    <Box sx={{ px: 2, py: 2 }}>
                      <Typography variant="body2" fontWeight={600} gutterBottom>
                        {col}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {summaryLoading
                          ? "Loading bounds…"
                          : "Statistics unavailable for this metric."}
                      </Typography>
                    </Box>
                  )}
                </Card>
              </Grid>
            );
          })}
        </Grid>

        <Stack direction="row" spacing={2} alignItems="center" sx={{ mt: 2 }}>
          <Button variant="contained" onClick={handleFilter}>
            Apply filter
          </Button>
          {appliedRules.length > 0 && (
            <Button variant="outlined" onClick={handleClearFilter}>
              Clear filter
            </Button>
          )}
          {filterResult && (
            <Stack direction="row" spacing={1} alignItems="center">
              <Chip label={`before: ${filterResult.before}`} variant="outlined" />
              <Chip label={`after: ${filterResult.after}`} color="primary" />
              <Chip
                label={`removed: ${filterResult.removed}`}
                color="warning"
                variant="outlined"
              />
              <Typography variant="body2" color="text.secondary">
                kept {(filterResult.kept_ratio * 100).toFixed(1)}%
              </Typography>
            </Stack>
          )}
        </Stack>
      </Paper>

      {/* Full-dataset summary table (Task 5) */}
      <Paper sx={{ p: 3, borderRadius: 3 }}>
        <Typography variant="h6" gutterBottom>
          Statistics summary (all rows)
        </Typography>
        <StatTable rows={summary} />
      </Paper>

      {/* Exports (Task 5) */}
      <Paper sx={{ p: 3, borderRadius: 3 }}>
        <Typography variant="h6" gutterBottom>
          Export pipeline
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Queue your filter rules, compute metrics for rows that are still empty,
          then export a filtered CSV where every row has been evaluated against
          your thresholds.
        </Typography>
        <Divider sx={{ mb: 2 }} />
        {message && (
          <Alert severity="success" sx={{ mb: 2, wordBreak: "break-all" }}>
            {message}
          </Alert>
        )}
        {exportQueue && (
          <Alert severity="info" sx={{ mb: 2 }}>
            <Stack spacing={0.5}>
              <Typography variant="body2">
                Export queue active · {exportQueue.pending_compute_rows?.toLocaleString() ?? "?"}{" "}
                rows still need metrics
                {exportQueue.filter && (
                  <>
                    {" "}
                    · filter passes {exportQueue.filter.after?.toLocaleString()} /{" "}
                    {exportQueue.filter.before?.toLocaleString()} evaluated rows
                  </>
                )}
              </Typography>
              {computeQueuedResult?.computed_rows != null && (
                <Typography variant="caption" color="text.secondary">
                  Last compute filled {computeQueuedResult.computed_rows.toLocaleString()} rows
                  ({computeQueuedResult.pending_compute_rows.toLocaleString()} still pending)
                </Typography>
              )}
            </Stack>
          </Alert>
        )}
        {busy && (
          <Box sx={{ mb: 2 }}>
            <LinearProgress />
            <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: "block" }}>
              Computing remaining metrics… this may take a while on large datasets.
            </Typography>
          </Box>
        )}
        <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap>
          <Button
            variant="outlined"
            startIcon={<QueueIcon />}
            disabled={busy}
            onClick={handleQueueExport}
          >
            Queue filter for export
          </Button>
          <Button
            variant="outlined"
            startIcon={<PlayArrowIcon />}
            disabled={busy || !exportQueue}
            onClick={handleComputeQueued}
          >
            Compute remaining metrics
          </Button>
          <Button
            variant="contained"
            startIcon={<DownloadIcon />}
            disabled={busy}
            onClick={handleFinalizeExport}
          >
            Compute & export CSV
          </Button>
          <Button
            variant="text"
            disabled={busy}
            onClick={handleExportCsv}
          >
            Export CSV only (skip compute)
          </Button>
          <Button
            variant="outlined"
            startIcon={<PictureAsPdfIcon />}
            disabled={busy}
            onClick={handleExportReport}
          >
            Export PDF report
          </Button>
        </Stack>
        {reportPreview && (
          <Box sx={{ mt: 3 }}>
            <Stack
              direction={{ xs: "column", sm: "row" }}
              justifyContent="space-between"
              alignItems={{ sm: "center" }}
              spacing={1}
              sx={{ mb: 1 }}
            >
              <Typography variant="subtitle2">
                Report preview · before {reportPreview.before} / after{" "}
                {reportPreview.after}
              </Typography>
              <Button
                size="small"
                href={reportPreview.url}
                target="_blank"
                rel="noopener noreferrer"
              >
                Open in new tab
              </Button>
            </Stack>
            <Box
              component="iframe"
              src={reportPreview.url}
              title="PDF report preview"
              sx={{
                width: "100%",
                height: { xs: 480, md: 720 },
                border: 1,
                borderColor: "divider",
                borderRadius: 2,
                bgcolor: "background.paper",
              }}
            />
          </Box>
        )}
      </Paper>
    </Stack>
  );
}
