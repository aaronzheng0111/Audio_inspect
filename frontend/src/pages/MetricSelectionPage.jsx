import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  LinearProgress,
  Stack,
  Typography,
} from "@mui/material";
import ScheduleIcon from "@mui/icons-material/Schedule";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import api from "../api/client.js";
import { useWizard } from "../context/WizardContext.jsx";

// Step 4 (Task 4): show predicted compute time, let the user confirm and run
// the calculation of the new metric columns.
export default function MetricSelectionPage() {
  const navigate = useNavigate();
  const {
    sessionId,
    selectedMetrics,
    setComputeResult,
    setActiveStep,
  } = useWizard();
  const [estimate, setEstimate] = useState(null);
  const [audioWarning, setAudioWarning] = useState("");
  const [error, setError] = useState("");
  const [computing, setComputing] = useState(false);

  useEffect(() => {
    setActiveStep(3);
    if (!sessionId || selectedMetrics.length === 0) {
      navigate("/mapping");
      return;
    }
    api
      .estimate(sessionId, selectedMetrics)
      .then((res) => {
        setEstimate(res);
        setAudioWarning(res.warning || "");
      })
      .catch((e) => setError(e.message));
  }, [sessionId, selectedMetrics, navigate, setActiveStep]);

  const handleCompute = async () => {
    setError("");
    setComputing(true);
    try {
      const result = await api.compute(sessionId, selectedMetrics);
      setComputeResult(result);
      navigate("/analysis");
    } catch (e) {
      setError(e.message);
    } finally {
      setComputing(false);
    }
  };

  return (
    <Box sx={{ maxWidth: 720, mx: "auto" }}>
      <Card>
        <CardContent>
          <Stack spacing={3} sx={{ p: 1 }}>
            <Typography variant="h5">Confirm computation</Typography>

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
                  Already in your CSV session — only new metrics will be computed.
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
                        {estimate.pending_metrics?.length
                          ? estimate.estimated_human
                          : "Already computed"}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        {estimate.pending_metrics?.length ? (
                          <>
                            Will compute {estimate.pending_metrics.join(", ")} for{" "}
                            {estimate.n_rows} files ({estimate.estimated_seconds}s)
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
                <Typography variant="caption" color="text.secondary">
                  Reading audio files and computing metrics… this can take a
                  while for large datasets.
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
                  : estimate?.pending_metrics?.length
                    ? "Compute new metrics"
                    : "Continue to analysis"}
              </Button>
            </Stack>
          </Stack>
        </CardContent>
      </Card>
    </Box>
  );
}
