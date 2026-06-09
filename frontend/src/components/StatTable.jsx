import {
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from "@mui/material";

// Full-dataset statistics summary (Task 5). Computed over all rows on the
// backend; only aggregate numbers are rendered so this stays lightweight.
const COLS = [
  ["column", "Column"],
  ["count", "Count"],
  ["missing", "Missing"],
  ["mean", "Mean"],
  ["std", "Std"],
  ["min", "Min"],
  ["p25", "P25"],
  ["median", "Median"],
  ["p75", "P75"],
  ["max", "Max"],
];

function fmt(v) {
  if (v === null || v === undefined) return "—";
  if (typeof v === "number") {
    return Math.abs(v) >= 1000 || (Math.abs(v) < 0.001 && v !== 0)
      ? v.toExponential(2)
      : v.toFixed(3).replace(/\.?0+$/, "");
  }
  return String(v);
}

export default function StatTable({ rows }) {
  if (!rows || rows.length === 0) {
    return (
      <Typography variant="body2" color="text.secondary">
        No numeric columns to summarise yet.
      </Typography>
    );
  }
  return (
    <TableContainer component={Paper} sx={{ borderRadius: 3 }}>
      <Table size="small">
        <TableHead>
          <TableRow>
            {COLS.map(([key, label]) => (
              <TableCell key={key} sx={{ fontWeight: 600 }}>
                {label}
              </TableCell>
            ))}
          </TableRow>
        </TableHead>
        <TableBody>
          {rows.map((row) => (
            <TableRow key={row.column} hover>
              {COLS.map(([key]) => (
                <TableCell
                  key={key}
                  sx={
                    key === "column"
                      ? { fontWeight: 600 }
                      : { fontFamily: "'Roboto Mono', monospace", fontSize: 12 }
                  }
                >
                  {key === "column" ? row[key] : fmt(row[key])}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}
