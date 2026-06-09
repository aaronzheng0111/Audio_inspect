import api from "../api/client.js";

const LABEL_OVERRIDES = {
  audio_name_id: "Audio name / ID",
  audio_name: "Audio name / ID",
  text: "Sentence",
  transcription: "Sentence",
  transcript: "Sentence",
  sentence: "Sentence",
  audio_path: "Audio path",
  sample_path: "Audio path",
  original_path: "Original path",
  duration_s: "Duration (s)",
  source: "Source",
};

const TEXT_COLUMNS = new Set([
  "text",
  "transcription",
  "transcript",
  "sentence",
  "label",
  "content",
]);
const NAME_COLUMNS = new Set(["audio_name_id", "audio_name", "id", "name", "filename"]);
const PATH_COLUMNS = new Set([
  "audio_path",
  "path",
  "sample_path",
  "original_path",
  "wav",
  "file",
]);

/** One clickable point on a scatter chart. */
export class PlotPoint {
  constructor(dataset, sourceIndex) {
    this.dataset = dataset;
    this.sourceIndex = sourceIndex;
  }

  get metricValue() {
    return this.dataset.values[this.sourceIndex];
  }

  get rowIndex() {
    return this.dataset.rowIndices[this.sourceIndex];
  }

  get metadata() {
    return this.dataset.rows[this.sourceIndex] || {};
  }

  audioUrl() {
    if (this.rowIndex === undefined || !this.dataset.sessionId) return null;
    return api.audioStreamUrl(this.dataset.sessionId, this.rowIndex);
  }

  sentenceText() {
    for (const key of TEXT_COLUMNS) {
      const value = this.metadata[key];
      if (value !== null && value !== undefined && String(value).trim()) {
        return String(value);
      }
    }
    return null;
  }

  hoverLabel() {
    const sentence = this.sentenceText();
    if (sentence) {
      const short = sentence.length > 80 ? `${sentence.slice(0, 80)}…` : sentence;
      return short;
    }
    for (const col of NAME_COLUMNS) {
      const value = this.metadata[col];
      if (value !== null && value !== undefined && String(value).trim()) {
        return String(value);
      }
    }
    return `Row ${this.rowIndex + 1}`;
  }

  metadataEntries() {
    const seen = new Set();
    const entries = [];

    const pushEntry = (column, value) => {
      if (seen.has(column)) return;
      seen.add(column);
      const display =
        value === null || value === undefined || value === "" ? "—" : String(value);
      entries.push({
        column,
        label: PlotDataset.formatLabel(column),
        value: display,
        isSentence: TEXT_COLUMNS.has(column),
        isPath: PATH_COLUMNS.has(column),
      });
    };

    for (const column of PlotDataset.orderMetadataColumns(this.dataset.metadataColumns)) {
      pushEntry(column, this.metadata[column]);
    }

    for (const [column, value] of Object.entries(this.metadata)) {
      pushEntry(column, value);
    }

    return entries;
  }
}

/** Plot sample returned by the analysis API for one metric column. */
export class PlotDataset {
  constructor({ sessionId, column, values, rowIndices, rows, metadataColumns }) {
    this.sessionId = sessionId;
    this.column = column;
    this.values = values || [];
    this.rowIndices = rowIndices || [];
    this.rows = rows || [];
    this.metadataColumns = metadataColumns || [];
  }

  static formatLabel(column) {
    return LABEL_OVERRIDES[column] || column.replace(/_/g, " ");
  }

  static orderMetadataColumns(columns) {
    const priority = (col) => {
      if (TEXT_COLUMNS.has(col)) return [0, col];
      if (NAME_COLUMNS.has(col)) return [1, col];
      if (PATH_COLUMNS.has(col)) return [3, col];
      return [2, col];
    };
    return [...columns].sort((a, b) => {
      const [pa, na] = priority(a);
      const [pb, nb] = priority(b);
      return pa - pb || na.localeCompare(nb);
    });
  }

  get numericValues() {
    return this.values.filter((v) => v !== null && v !== undefined);
  }

  get scatterPoints() {
    return this.values
      .map((value, sourceIndex) => ({ value, sourceIndex }))
      .filter((point) => point.value !== null && point.value !== undefined);
  }

  pointAt(sourceIndex) {
    if (sourceIndex === null || sourceIndex === undefined) return null;
    return new PlotPoint(this, sourceIndex);
  }

  hoverLabels() {
    return this.scatterPoints.map((point) => this.pointAt(point.sourceIndex).hoverLabel());
  }
}
