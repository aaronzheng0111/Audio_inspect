import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  FormControl,
  InputLabel,
  LinearProgress,
  MenuItem,
  Select,
  Stack,
  Typography,
} from "@mui/material";
import ScheduleIcon from "@mui/icons-material/Schedule";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import api from "../api/client.js";
import { useWizard } from "../context/WizardContext.jsx";

const ROW_LIMIT_OPTIONS = [
  { label: "100", value: 100 },
  { label: "500", value: 500 },
  { label: "1,000", value: 1000 },
  { label: "2,000", value: 2000 },
  { label: "5,000", value: 5000 },
  { label: "10,000", value: 10000 },
  { label: "All rows", value: null },
];

function defaultRowLimit(nRows) {
  if (!nRows || nRows <= 5000) return null;
  return 2000;
}

// Step 4 (Task 4): show predicted compute time, let the user confirm and run
// the calculation of the new metric columns.
export default function MetricSelectionPage() {
  const navigate = useNavigate();
  const {
    sessionId,
    selectedMetrics,
    datasetInfo,
    setComputeResult,
    setActiveStep,
  } = useWizard();
  const [estimate, setEstimate] = useState(null);
  const [audioWarning, setAudioWarning] = useState("");
  const [error, setError] = useState("");
  const [computing, setComputing] = useState(false);
  const [rowLimit, setRowLimit] = useState(null);
  const [rowStrategy, setRowStrategy] = useState("first");
  const [limitInitialized, setLimitInitialized] = useState(false);

  const nRows = datasetInfo?.n_rows ?? estimate?.total_rows;

  useEffect(() => {
    if (!limitInitialized && nRows) {
      setRowLimit(defaultRowLimit(nRows));
      setLimitInitialized(true);
    }
  }, [nRows, limitInitialized]);

  const loadEstimate = useCallback(async () => {
    const res = await api.estimate(sessionId, selectedMetrics, {
      rowLimit,
      rowStrategy,
    });
    setEstimate(res);
    setAudioWarning(res.warning || "");
  }, [sessionId, selectedMetrics, rowLimit, rowStrategy]);

  useEffect(() => {
    setActiveStep(3);
    if (!sessionId || selectedMetrics.length === 0) {
      navigate("/mapping");
      return;
    }
    loadEstimate().catch((e) => setError(e.message));
  }, [sessionId, selectedMetrics, navigate, setActiveStep, loadEstimate]);

  const rowLimitChoices = useMemo(() => {
    const opts = ROW_LIMIT_OPTIONS.filter(
      (o) => o.value === null || !nRows || o.value <= nRows
    );
    return opts.length ? opts : ROW_LIMIT_OPTIONS;
  }, [nRows]);

  const handleCompute = async () => {
    setError("");
    setComputing(true);
    try {
      const result = await api.compute(sessionId, selectedMetrics, {
        rowLimit,
        rowStrategy,
      });
      setComputeResult(result);
      navigate("/analysis");
    } catch (e) {
      setError(e.message);
    } finally {
      setComputing(false);
    }
  };

  const pendingCount = estimate?.pending_metrics?.length ?? 0;
  const computeRows = estimate?.compute_rows ?? 0;
  const isPartial =
    rowLimit !== null && nRows && computeRows > 0 && computeRows < nRows;

  return (
    <Box sx={{ maxWidth: 720, mx: "auto" }}>
      <Card>
        <CardContent>
          <Stack spacing={3} sx={{ p: 1 }}>
            <Typography variant="h5">Confirm computation</Typography>

            <Box>
              <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                Rows to compute
              </Typography>
              <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
                <FormControl size="small" sx={{ minWidth: 160 }}>
                  <InputLabel>Sample size</InputLabel>
                  <Select
                    label="Sample size"
                    value={rowLimit === null ? "all" : rowLimit}
                    onChange={(e) => {
                      const v = e.target.value;
                      setRowLimit(v === "all" ? null : Number(v));
                    }}
                  >
                    {rowLimitChoices.map((o) => (
                      <MenuItem
                        key={o.label}
                        value={o.value === null ? "all" : o.value}
                      >
                        {o.label}
                        {o.value === null && nRows
                          ? ` (${nRows.toLocaleString()})`
                          : ""}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
                <FormControl size="small" sx={{ minWidth: 160 }}>
                  <InputLabel>Strategy</InputLabel>
                  <Select
                    label="Strategy"
                    value={rowStrategy}
                    onChange={(e) => setRowStrategy(e.target.value)}
                    disabled={rowLimit === null}
                  >
                    <MenuItem value="first">First N rows</MenuItem>
                    <MenuItem value="random">Random sample</MenuItem>
                  </Select>
                </FormControl>
              </Stack>
              {isPartial && (
                <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: "block" }}>
                  Metrics will be computed for {computeRows.toLocaleString()} of{" "}
                  {nRows?.toLocaleString()} rows this run. Remaining rows stay
                  empty until you compute again with a higher limit or &quot;All
                  rows&quot;.
                </Typography>
              )}
            </Box>

            <Box>
              <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                Selected metrics
              </Typography>
              <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                {selectedMetrics.map((m) => {
                  const done = estimate?.skipped_metrics?.includes(m);
                  return (
                    <Chip
                      key={m}
                      label={done ? `${m} (computed)` : m}
                      color={done ? "success" : "primary"}
                      variant={done ? "filled" : "outlined"}
                    />
                  );
                })}
              </Stack>
              {estimate?.skipped_metrics?.length > 0 && (
                <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: "block" }}>
                  Already in your CSV — only new metrics will be computed.
                </Typography>
              )}
              {datasetInfo?.partial_metrics?.length > 0 && (
                <Typography variant="caption" color="warning.main" sx={{ mt: 1, display: "block" }}>
                  Partially computed (will resume):{" "}
                  {datasetInfo.partial_metrics.join(", ")}
                </Typography>
              )}
            </Box>

            <Card variant="outlined" sx={{ bgcolor: "rgba(25,118,210,0.04)" }}>
              <CardContent>
                <Stack direction="row" alignItems="center" spacing={1.5}>
                  <ScheduleIcon color="primary" />
                  {estimate ? (
                    <Box>
                      <Typography variant="h6">
                        {pendingCount ? estimate.estimated_human : "Already computed"}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        {pendingCount ? (
                          <>
                            Will compute {estimate.pending_metrics.join(", ")} for{" "}
                            {computeRows.toLocaleString()} file
                            {computeRows === 1 ? "" : "s"}
                            {estimate.estimated_seconds >= 60
                              ? ` (~${Math.round(estimate.estimated_seconds / 60)} min)`
                              : ` (~${Math.round(estimate.estimated_seconds)} s)`}
                          </>
                        ) : (
                          <>All selected metrics are already in the dataset.</>
                        )}
                      </Typography>
                    </Box>
                  ) : (
                    <Typography variant="body2" color="text.secondary">
                      Estimating…
                    </Typography>
                  )}
                </Stack>
              </CardContent>
            </Card>

            {audioWarning && (
              <Alert severity="warning">
                {audioWarning}
                {estimate?.example_resolved_path && (
                  <>
                    <br />
                    <Typography component="span" variant="caption" sx={{ fontFamily: "'Roboto Mono', monospace" }}>
                      Example: {estimate.example_resolved_path}
                    </Typography>
                  </>
                )}
              </Alert>
            )}

            {computing && (
              <Box>
                <LinearProgress />
                <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: "block" }}>
                  Computing metrics for {computeRows.toLocaleString()} rows…
                </Typography>
              </Box>
            )}

            {error && <Alert severity="error">{error}</Alert>}

            <Stack direction="row" justifyContent="space-between">
              <Button
                startIcon={<ArrowBackIcon />}
                disabled={computing}
                onClick={() => navigate("/mapping")}
              >
                Back
              </Button>
              <Button
                variant="contained"
                startIcon={computing ? <CircularProgress size={18} /> : <PlayArrowIcon />}
                disabled={computing || !estimate}
                onClick={handleCompute}
              >
                {computing
                  ? "Computing…"
                  : pendingCount
                    ? "Compute metrics"
                    : "Continue to analysis"}
              </Button>
            </Stack>
          </Stack>
        </CardContent>
      </Card>
    </Box>
  );
}
