import { createTheme } from "@mui/material/styles";

// Material Design theme for Audio Inspect.
// Design intent (from Generater/02 Plan.md):
//   - Follow Google Material Design.
//   - "Less is more": restrained type scale, generous spacing.
//   - Layered surfaces (elevation) to give the UI depth.
//   - A subtle background texture so it reads as fashion / tech / professional.
const theme = createTheme({
  palette: {
    mode: "light",
    primary: { main: "#1976d2" },
    secondary: { main: "#00bfa5" },
    background: {
      default: "#eef2f7",
      paper: "#ffffff",
    },
    text: {
      primary: "#1a2027",
      secondary: "#5b6b7b",
    },
  },
  shape: { borderRadius: 14 },
  typography: {
    fontFamily: "Roboto, system-ui, sans-serif",
    h4: { fontWeight: 500, letterSpacing: "-0.5px" },
    h5: { fontWeight: 500 },
    h6: { fontWeight: 500 },
    button: { textTransform: "none", fontWeight: 500 },
    // Monospace for paths and numbers keeps tabular data legible.
    fontFamilyMono: "'Roboto Mono', monospace",
  },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: {
          // Layered radial tints + a faint grid texture for depth.
          backgroundImage: [
            "radial-gradient(circle at 15% 15%, rgba(25,118,210,0.10), transparent 40%)",
            "radial-gradient(circle at 85% 0%, rgba(0,191,165,0.10), transparent 35%)",
            "linear-gradient(rgba(0,0,0,0.015) 1px, transparent 1px)",
            "linear-gradient(90deg, rgba(0,0,0,0.015) 1px, transparent 1px)",
          ].join(","),
          backgroundSize: "100% 100%, 100% 100%, 24px 24px, 24px 24px",
          backgroundAttachment: "fixed",
          minHeight: "100vh",
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: { backgroundImage: "none" },
      },
    },
    MuiCard: {
      defaultProps: { elevation: 2 },
      styleOverrides: {
        root: {
          border: "1px solid rgba(0,0,0,0.05)",
          backdropFilter: "saturate(1.05)",
        },
      },
    },
    MuiButton: {
      defaultProps: { disableElevation: true },
    },
  },
});

export default theme;
