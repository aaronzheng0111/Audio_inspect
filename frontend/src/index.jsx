import React from "react";
import ReactDOM from "react-dom/client";
import { CssBaseline, ThemeProvider } from "@mui/material";
import App from "./App.jsx";
import theme from "./theme/theme.js";
import { WizardProvider } from "./context/WizardContext.jsx";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <WizardProvider>
        <App />
      </WizardProvider>
    </ThemeProvider>
  </React.StrictMode>
);
