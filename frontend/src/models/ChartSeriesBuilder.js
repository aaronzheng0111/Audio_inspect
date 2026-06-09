/** Build Plotly trace objects for a metric chart card. */
export class ChartSeriesBuilder {
  constructor(dataset) {
    this.dataset = dataset;
  }

  build(chartType, { selectedSourceIndex = null, xValues = null } = {}) {
    switch (chartType) {
      case "scatter":
        return this._scatter(selectedSourceIndex, xValues);
      case "bar":
        return this._bar();
      case "box":
        return this._box();
      case "histogram":
      default:
        return this._histogram();
    }
  }

  _scatter(selectedSourceIndex, xValues) {
    const points = this.dataset.scatterPoints;
    const baseColor = "#1976d2";
    const selectedColor = "#d32f2f";
    return [
      {
        x: xValues || points.map((_, i) => i),
        y: points.map((point) => point.value),
        customdata: points.map((point) => point.sourceIndex),
        type: "scattergl",
        mode: "markers",
        marker: {
          color: points.map((point) =>
            point.sourceIndex === selectedSourceIndex ? selectedColor : baseColor
          ),
          size: points.map((point) => (point.sourceIndex === selectedSourceIndex ? 9 : 5)),
          opacity: 0.75,
          line: { width: 0 },
        },
        text: this.dataset.hoverLabels(),
        hovertemplate: "%{text}<br>%{y}<extra></extra>",
      },
    ];
  }

  _bar() {
    const values = this.dataset.numericValues;
    return [
      {
        x: values.map((_, i) => i),
        y: values,
        type: "bar",
        marker: { color: "#1976d2" },
      },
    ];
  }

  _box() {
    return [
      {
        y: this.dataset.numericValues,
        type: "box",
        marker: { color: "#1976d2" },
        boxpoints: "outliers",
      },
    ];
  }

  _histogram() {
    return [
      {
        x: this.dataset.numericValues,
        type: "histogram",
        marker: { color: "#1976d2" },
        nbinsx: 30,
      },
    ];
  }
}
