import { useMemo, useState } from "react";
import {
  Card,
  CardContent,
  CardHeader,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Stack,
} from "@mui/material";
import Plot from "react-plotly.js";

// A single chart card. Each numeric attribute gets its own card (Task 5). The
// user can switch the chart type per card (histogram / scatter / bar / box).
const CHART_TYPES = ["histogram", "box", "scatter", "bar"];

export default function PlotCard({ column, values, index, xValues }) {
  const [chartType, setChartType] = useState("histogram");

  const numeric = useMemo(
    () => (values || []).filter((v) => v !== null && v !== undefined),
    [values]
  );

  const data = useMemo(() => {
    const color = "#1976d2";
    switch (chartType) {
      case "scatter":
        return [
          {
            x: xValues || numeric.map((_, i) => i),
            y: numeric,
            type: "scattergl",
            mode: "markers",
            marker: { color, size: 5, opacity: 0.6 },
          },
        ];
      case "bar":
        return [
          {
            x: numeric.map((_, i) => i),
            y: numeric,
            type: "bar",
            marker: { color },
          },
        ];
      case "box":
        return [{ y: numeric, type: "box", marker: { color }, boxpoints: "outliers" }];
      case "histogram":
      default:
        return [{ x: numeric, type: "histogram", marker: { color }, nbinsx: 30 }];
    }
  }, [chartType, numeric, xValues]);

  return (
    <Card sx={{ height: "100%" }}>
      <CardHeader
        title={column}
        titleTypographyProps={{ variant: "subtitle1", fontWeight: 600 }}
        action={
          <FormControl size="small" sx={{ minWidth: 130 }}>
            <InputLabel>Chart</InputLabel>
            <Select
              label="Chart"
              value={chartType}
              onChange={(e) => setChartType(e.target.value)}
            >
              {CHART_TYPES.map((t) => (
                <MenuItem key={t} value={t}>
                  {t}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        }
      />
      <CardContent>
        <Stack>
          <Plot
            data={data}
            layout={{
              autosize: true,
              height: 280,
              margin: { l: 40, r: 16, t: 10, b: 36 },
              paper_bgcolor: "transparent",
              plot_bgcolor: "transparent",
              font: { family: "Roboto, sans-serif", size: 11 },
            }}
            config={{ displayModeBar: false, responsive: true }}
            style={{ width: "100%" }}
            useResizeHandler
          />
        </Stack>
      </CardContent>
    </Card>
  );
}
