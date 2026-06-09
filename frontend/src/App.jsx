import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AppBar, Box, Container, Toolbar, Typography } from "@mui/material";
import GraphicEqIcon from "@mui/icons-material/GraphicEq";
import StepperBar from "./components/StepperBar.jsx";
import PathInputPage from "./pages/PathInputPage.jsx";
import CsvPreviewPage from "./pages/CsvPreviewPage.jsx";
import AttributeMappingPage from "./pages/AttributeMappingPage.jsx";
import MetricSelectionPage from "./pages/MetricSelectionPage.jsx";
import AnalysisPage from "./pages/AnalysisPage.jsx";

export default function App() {
  return (
    <BrowserRouter
      future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
    >
      <AppBar position="sticky" color="default" elevation={1}>
        <Toolbar>
          <GraphicEqIcon color="primary" sx={{ mr: 1.5 }} />
          <Typography variant="h6" sx={{ flexGrow: 1, fontWeight: 600 }}>
            Audio Inspect
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Audio dataset cleaning & analysis
          </Typography>
        </Toolbar>
      </AppBar>

      <Container maxWidth="lg" sx={{ py: 4 }}>
        <StepperBar />
        <Box sx={{ mt: 4 }}>
          <Routes>
            <Route path="/" element={<PathInputPage />} />
            <Route path="/preview" element={<CsvPreviewPage />} />
            <Route path="/mapping" element={<AttributeMappingPage />} />
            <Route path="/metrics" element={<MetricSelectionPage />} />
            <Route path="/analysis" element={<AnalysisPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Box>
      </Container>
    </BrowserRouter>
  );
}
