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
  MenuItem,
  Paper,
  Select,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import RestartAltIcon from "@mui/icons-material/RestartAlt";
import DownloadIcon from "@mui/icons-material/Download";
import PictureAsPdfIcon from "@mui/icons-material/PictureAsPdf";
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
  const [filterResult, setFilterResult] = useState(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  // Only chart the metrics the user computed (fall back to all numeric columns).
  const metricColumns = useMemo(
    () => (selectedMetrics.length ? selectedMetrics : summary.map((s) => s.column)),
    [selectedMetrics, summary]
  );

  // Min/max for filter sliders follow the currently rendered chart sample so
  // bounds stay in sync when the user changes sample size or strategy.
  const plotBounds = useMemo(() => {
    const out = {};
    if (!plot?.data) return out;
    for (const col of metricColumns) {
      const values = (plot.data[col] || []).filter(
        (v) => v !== null && v !== undefined && Number.isFinite(Number(v))
      );
      if (values.length) {
        out[col] = {
          min: Math.min(...values),
          max: Math.max(...values),
        };
      }
    }
    return out;
  }, [plot, metricColumns]);

  const boundsFor = useCallback(
    (column) => {
      if (plotBounds[column]) return plotBounds[column];
      const row = summary.find((s) => s.column === column);
      if (row?.min == null || row?.max == null) return null;
      return { min: row.min, max: row.max };
    },
    [plotBounds, summary]
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
    const res = await api.plotData(sessionId, metricColumns, limit, strategy);
    setPlot(res);
  }, [sessionId, metricColumns, limit, strategy]);

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

  // Keep slider positions aligned with the visible sample when it changes.
  useEffect(() => {
    if (!plot?.data || Object.keys(plotBounds).length === 0) return;
    setRules((prev) => {
      const next = { ...prev };
      let changed = false;
      for (const col of metricColumns) {
        const bounds = plotBounds[col];
        if (!bounds) continue;
        const existing = prev[col];
        if (
          !existing ||
          existing.min !== bounds.min ||
          existing.max !== bounds.max
        ) {
          next[col] = { column: col, min: bounds.min, max: bounds.max };
          changed = true;
        }
      }
      return changed ? next : prev;
    });
    setFilterResult(null);
  }, [plot, plotBounds, metricColumns, limit, strategy]);

  const ruleList = () =>
    Object.values(rules).filter(
      (r) => r && (r.min !== undefined || r.max !== undefined)
    );

  const handleFilter = async () => {
    setError("");
    try {
      const res = await api.filter(sessionId, ruleList());
      setFilterResult(res);
    } catch (e) {
      setError(e.message);
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
    setBusy(true);
    try {
      const res = await api.exportReport(sessionId, ruleList());
      setMessage(
        `PDF report written (before ${res.before} / after ${res.after}): ${res.path}`
      );
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
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
            {computeResult.approximate?.length
              ? ` · approx: ${computeResult.approximate.join(", ")}`
              : ""}
          </Typography>
        </Box>
        <Button startIcon={<RestartAltIcon />} onClick={startOver}>
          Start over
        </Button>
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
              label={`showing ${plot.returned_rows} of ${plot.total_rows}`}
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
          Adjust thresholds per metric, then apply to see how many rows remain.
          Slider ranges follow the currently displayed sample; filtering still
          applies to the full dataset.
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
                      key={`${col}-${limit}-${strategy}-${bounds.min}-${bounds.max}`}
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
          Export
        </Typography>
        <Divider sx={{ mb: 2 }} />
        {message && (
          <Alert severity="success" sx={{ mb: 2, wordBreak: "break-all" }}>
            {message}
          </Alert>
        )}
        <Stack direction="row" spacing={2}>
          <Button
            variant="outlined"
            startIcon={<DownloadIcon />}
            disabled={busy}
            onClick={handleExportCsv}
          >
            Export filtered CSV
          </Button>
          <Button
            variant="contained"
            startIcon={<PictureAsPdfIcon />}
            disabled={busy}
            onClick={handleExportReport}
          >
            Export PDF report
          </Button>
        </Stack>
      </Paper>
    </Stack>
  );
}
