import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import FolderOpenIcon from "@mui/icons-material/FolderOpen";
import api from "../api/client.js";
import { useWizard } from "../context/WizardContext.jsx";

// Step 1 (Task 1): the user enters the path to the dataset CSV on disk.
export default function PathInputPage() {
  const navigate = useNavigate();
  const {
    csvPath,
    setCsvPath,
    setSessionId,
    setDatasetInfo,
    setMapping,
    setActiveStep,
  } = useWizard();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => setActiveStep(0), [setActiveStep]);

  const handleLoad = async () => {
    setError("");
    setLoading(true);
    try {
      const info = await api.loadDataset(csvPath.trim());
      setSessionId(info.session_id);
      setDatasetInfo(info);
      setMapping(info.suggested_mapping || {});
      navigate("/preview");
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
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
              {loading ? "Loading…" : "Load dataset"}
            </Button>
          </Stack>
        </CardContent>
      </Card>
    </Box>
  );
}
