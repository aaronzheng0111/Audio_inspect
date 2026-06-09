import { Paper, Step, StepLabel, Stepper } from "@mui/material";
import { useWizard, STEPS } from "../context/WizardContext.jsx";

// Visual progress indicator across the 5 wizard steps. Reads the active step
// from the shared wizard state so every page stays in sync.
export default function StepperBar() {
  const { activeStep } = useWizard();
  return (
    <Paper elevation={1} sx={{ p: 2, borderRadius: 3 }}>
      <Stepper activeStep={activeStep} alternativeLabel>
        {STEPS.map((label) => (
          <Step key={label}>
            <StepLabel>{label}</StepLabel>
          </Step>
        ))}
      </Stepper>
    </Paper>
  );
}
