import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  Box,
  Button,
  Chip,
  Stack,
  Typography,
} from "@mui/material";
import ArrowForwardIcon from "@mui/icons-material/ArrowForward";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import CsvTable from "../components/CsvTable.jsx";
import { useWizard } from "../context/WizardContext.jsx";

// Step 2 (Task 2): show CSV details + a small sample (~15 rows) of the data.
export default function CsvPreviewPage() {
  const navigate = useNavigate();
  const { datasetInfo, setActiveStep } = useWizard();

  useEffect(() => {
    setActiveStep(1);
    if (!datasetInfo) navigate("/");
  }, [datasetInfo, navigate, setActiveStep]);

  if (!datasetInfo) return null;

  return (
    <Box>
      <Stack
        direction={{ xs: "column", sm: "row" }}
        justifyContent="space-between"
        alignItems={{ sm: "center" }}
        spacing={1}
        sx={{ mb: 2 }}
      >
        <Box>
          <Typography variant="h5">Dataset preview</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ fontFamily: "'Roboto Mono', monospace" }}>
            {datasetInfo.csv_path}
          </Typography>
        </Box>
        <Stack direction="row" spacing={1}>
          <Chip label={`${datasetInfo.n_rows} rows`} color="primary" />
          <Chip label={`${datasetInfo.columns.length} columns`} variant="outlined" />
          <Chip label={`showing ${datasetInfo.sample.length}`} variant="outlined" />
        </Stack>
      </Stack>

      <CsvTable columns={datasetInfo.columns} rows={datasetInfo.sample} />

      <Stack direction="row" justifyContent="space-between" sx={{ mt: 3 }}>
        <Button startIcon={<ArrowBackIcon />} onClick={() => navigate("/")}>
          Back
        </Button>
        <Button
          variant="contained"
          endIcon={<ArrowForwardIcon />}
          onClick={() => navigate("/mapping")}
        >
          Map attributes
        </Button>
      </Stack>
    </Box>
  );
}
