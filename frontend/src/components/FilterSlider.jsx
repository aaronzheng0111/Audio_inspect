import { Box, Grid, Slider, Stack, TextField, Typography } from "@mui/material";

// A min/max range control for one metric column. The user can drag the slider
// or type exact values (Task 5: "slide bar and could type the value"). Bounds
// come from the column's observed min/max in the current chart sample.
export default function FilterSlider({ column, bounds, value, onChange }) {
  const { min, max } = bounds;
  const step = max > min ? (max - min) / 100 : 1;
  const current = [
    value?.min ?? min,
    value?.max ?? max,
  ];

  const handleSlider = (_, newValue) => {
    onChange({ column, min: newValue[0], max: newValue[1] });
  };

  const handleField = (which, raw) => {
    const num = raw === "" ? (which === "min" ? min : max) : Number(raw);
    onChange({
      column,
      min: which === "min" ? num : current[0],
      max: which === "max" ? num : current[1],
    });
  };

  return (
    <Box sx={{ px: 1, py: 1 }}>
      <Typography variant="body2" fontWeight={600} gutterBottom>
        {column}
      </Typography>
      <Stack spacing={1}>
        <Slider
          size="small"
          value={current}
          min={min}
          max={max}
          step={step}
          onChange={handleSlider}
          valueLabelDisplay="auto"
        />
        <Grid container spacing={1}>
          <Grid item xs={6}>
            <TextField
              label="min"
              type="number"
              size="small"
              fullWidth
              value={current[0]}
              onChange={(e) => handleField("min", e.target.value)}
            />
          </Grid>
          <Grid item xs={6}>
            <TextField
              label="max"
              type="number"
              size="small"
              fullWidth
              value={current[1]}
              onChange={(e) => handleField("max", e.target.value)}
            />
          </Grid>
        </Grid>
      </Stack>
    </Box>
  );
}
