import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  InputAdornment,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import FolderOpenIcon from "@mui/icons-material/FolderOpen";
import api from "../api/client.js";
import FileBrowserDialog from "../components/FileBrowserDialog.jsx";
import { useWizard } from "../context/WizardContext.jsx";

// Step 1 (Task 1): the user provides the path to the dataset CSV on disk.
// They can either type it manually or click Browse to pick it from a
// file-system navigator powered by the backend.
export default function PathInputPage() {
  const navigate = useNavigate();
  const {
    csvPath,
    setCsvPath,
    setSessionId,
    setDatasetInfo,
    setMapping,
    setSelectedMetrics,
    setActiveStep,
  } = useWizard();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [browserOpen, setBrowserOpen] = useState(false);

  useEffect(() => setActiveStep(0), [setActiveStep]);

  const handleLoad = async () => {
    setError("");
    setLoading(true);
    try {
      const info = await api.loadDataset(csvPath.trim());
      setSessionId(info.session_id);
      setDatasetInfo(info);
      setMapping(info.suggested_mapping || {});
      // Pre-select any metrics already present in the CSV from a prior session.
      if (info.pre_computed_metrics?.length) {
        setSelectedMetrics(info.pre_computed_metrics);
      }
      navigate("/preview");
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const handleFileSelected = (path) => {
    setCsvPath(path);
  };

  return (
    <Box sx={{ maxWidth: 720, mx: "auto" }}>
      <Card>
        <CardContent>
          <Stack spacing={3} sx={{ p: 1 }}>
            <Box>
              <Typography variant="h4" gutterBottom>
                Load an audio dataset
              </Typography>
              <Typography variant="body1" color="text.secondary">
                Point Audio Inspect at a CSV that describes your audio dataset.
                We'll preview it, then help you compute acoustic quality metrics
                and filter the data.
              </Typography>
            </Box>

            <TextField
              label="CSV file path"
              placeholder="/path/to/dataset.csv"
              fullWidth
              value={csvPath}
              onChange={(e) => setCsvPath(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && csvPath && handleLoad()}
              InputProps={{
                startAdornment: (
                  <FolderOpenIcon sx={{ mr: 1, color: "text.secondary" }} />
                ),
                endAdornment: (
                  <InputAdornment position="end">
                    <Button
                      size="small"
                      variant="outlined"
                      onClick={() => setBrowserOpen(true)}
                    >
                      Browse
                    </Button>
                  </InputAdornment>
                ),
                sx: { fontFamily: "'Roboto Mono', monospace" },
              }}
            />

            {error && <Alert severity="error">{error}</Alert>}

            <Button
              variant="contained"
              size="large"
              disabled={!csvPath.trim() || loading}
              onClick={handleLoad}
            >
              {loading ? "Loading CSV (large files may take a minute)…" : "Load dataset"}
            </Button>
          </Stack>
        </CardContent>
      </Card>

      <FileBrowserDialog
        open={browserOpen}
        onClose={() => setBrowserOpen(false)}
        onSelect={handleFileSelected}
      />
    </Box>
  );
}
