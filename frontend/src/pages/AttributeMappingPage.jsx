import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Alert,
  Box,
  Button,
  Divider,
  Paper,
  Stack,
  Typography,
} from "@mui/material";
import ArrowForwardIcon from "@mui/icons-material/ArrowForward";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import AttributeMapper from "../components/AttributeMapper.jsx";
import MetricSelector from "../components/MetricSelector.jsx";
import api from "../api/client.js";
import { useWizard } from "../context/WizardContext.jsx";

// Step 3 (Task 3): map required attributes and pick which metrics to generate.
export default function AttributeMappingPage() {
  const navigate = useNavigate();
  const {
    sessionId,
    datasetInfo,
    mapping,
    setMapping,
    selectedMetrics,
    setSelectedMetrics,
    setActiveStep,
  } = useWizard();
  const [metrics, setMetrics] = useState([]);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setActiveStep(2);
    if (!datasetInfo) {
      navigate("/");
      return;
    }
    api
      .listMetrics()
      .then((res) => setMetrics(res.metrics))
      .catch((e) => setError(e.message));
  }, [datasetInfo, navigate, setActiveStep]);

  if (!datasetInfo) return null;

  const handleNext = async () => {
    setError("");
    if (!mapping.audio_path) {
      setError("Please map a column to 'audio_path' before continuing.");
      return;
    }
    if (selectedMetrics.length === 0) {
      setError("Select at least one metric to generate.");
      return;
    }
    setSaving(true);
    try {
      await api.mapAttributes(sessionId, mapping);
      navigate("/metrics");
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Stack spacing={3}>
      <Paper sx={{ p: 3, borderRadius: 3 }}>
        <Typography variant="h6" gutterBottom>
          1. Map required attributes
        </Typography>
        <AttributeMapper
          columns={datasetInfo.columns}
          mapping={mapping}
          onChange={setMapping}
        />
      </Paper>

      <Paper sx={{ p: 3, borderRadius: 3 }}>
        <Typography variant="h6" gutterBottom>
          2. Select metrics to generate
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Pick the acoustic quality metrics to compute from the audio files.
          Metrics flagged <b>approx</b> are approximations of complex measures.
        </Typography>
        <Divider sx={{ mb: 2 }} />
        <MetricSelector
          metrics={metrics}
          selected={selectedMetrics}
          onChange={setSelectedMetrics}
        />
      </Paper>

      {error && <Alert severity="error">{error}</Alert>}

      <Stack direction="row" justifyContent="space-between">
        <Button startIcon={<ArrowBackIcon />} onClick={() => navigate("/preview")}>
          Back
        </Button>
        <Button
          variant="contained"
          endIcon={<ArrowForwardIcon />}
          disabled={saving}
          onClick={handleNext}
        >
          {saving ? "Saving…" : "Estimate & compute"}
        </Button>
      </Stack>
    </Stack>
  );
}
