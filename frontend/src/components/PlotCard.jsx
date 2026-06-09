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
import ScatterPointPanel from "./ScatterPointPanel.jsx";
import { ChartSeriesBuilder } from "../models/ChartSeriesBuilder.js";
import { PlotDataset } from "../models/PlotDataset.js";

const CHART_TYPES = ["histogram", "box", "scatter", "bar"];

export default function PlotCard({
  column,
  values,
  index,
  xValues,
  sessionId,
  rowIndices,
  rows,
  metadataColumns,
}) {
  const [chartType, setChartType] = useState("histogram");
  const [selectedSourceIndex, setSelectedSourceIndex] = useState(null);

  const dataset = useMemo(
    () =>
      new PlotDataset({
        sessionId,
        column,
        values,
        rowIndices,
        rows,
        metadataColumns,
      }),
    [sessionId, column, values, rowIndices, rows, metadataColumns]
  );

  const chartData = useMemo(
    () =>
      new ChartSeriesBuilder(dataset).build(chartType, {
        selectedSourceIndex,
        xValues,
      }),
    [dataset, chartType, selectedSourceIndex, xValues]
  );

  const selectedPoint = dataset.pointAt(selectedSourceIndex);

  const handlePlotClick = (event) => {
    if (chartType !== "scatter" || !event?.points?.length) return;
    const sourceIndex = event.points[0].customdata;
    if (sourceIndex === undefined || sourceIndex === null) return;
    setSelectedSourceIndex(sourceIndex);
  };

  const handleChartTypeChange = (nextType) => {
    setChartType(nextType);
    setSelectedSourceIndex(null);
  };

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
              onChange={(e) => handleChartTypeChange(e.target.value)}
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
        <Stack spacing={2}>
          <Plot
            data={chartData}
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
            onClick={handlePlotClick}
          />
          {chartType === "scatter" && <ScatterPointPanel point={selectedPoint} />}
        </Stack>
      </CardContent>
    </Card>
  );
}
