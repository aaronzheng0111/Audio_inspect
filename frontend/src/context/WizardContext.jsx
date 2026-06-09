import { createContext, useContext, useMemo, useState } from "react";

// Shared state for the 5-step wizard. Holds the backend session id and every
// selection the user makes, so each page can read/update without prop drilling.
const WizardContext = createContext(null);

export const STEPS = [
  "Input CSV",
  "Preview",
  "Map & select",
  "Compute",
  "Analyse",
];

export function WizardProvider({ children }) {
  const [sessionId, setSessionId] = useState(null);
  const [csvPath, setCsvPath] = useState("");
  const [datasetInfo, setDatasetInfo] = useState(null); // /dataset/load response
  const [mapping, setMapping] = useState({}); // canonical -> column
  const [selectedMetrics, setSelectedMetrics] = useState([]);
  const [computeResult, setComputeResult] = useState(null);
  const [activeStep, setActiveStep] = useState(0);

  const reset = () => {
    setSessionId(null);
    setCsvPath("");
    setDatasetInfo(null);
    setMapping({});
    setSelectedMetrics([]);
    setComputeResult(null);
    setActiveStep(0);
  };

  const value = useMemo(
    () => ({
      sessionId,
      setSessionId,
      csvPath,
      setCsvPath,
      datasetInfo,
      setDatasetInfo,
      mapping,
      setMapping,
      selectedMetrics,
      setSelectedMetrics,
      computeResult,
      setComputeResult,
      activeStep,
      setActiveStep,
      reset,
    }),
    [
      sessionId,
      csvPath,
      datasetInfo,
      mapping,
      selectedMetrics,
      computeResult,
      activeStep,
    ]
  );

  return (
    <WizardContext.Provider value={value}>{children}</WizardContext.Provider>
  );
}

export function useWizard() {
  const ctx = useContext(WizardContext);
  if (!ctx) {
    throw new Error("useWizard must be used inside <WizardProvider>");
  }
  return ctx;
}
