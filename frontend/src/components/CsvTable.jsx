import {
  Chip,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
} from "@mui/material";

// Renders the CSV preview: a compact sample of rows (~15) with column headers
// annotated by their inferred type. Used on the Preview page (Task 2).
export default function CsvTable({ columns, rows }) {
  if (!columns || columns.length === 0) return null;
  const names = columns.map((c) => c.name);

  return (
    <TableContainer component={Paper} sx={{ maxHeight: 480, borderRadius: 3 }}>
      <Table stickyHeader size="small">
        <TableHead>
          <TableRow>
            {columns.map((col) => (
              <TableCell key={col.name} sx={{ fontWeight: 600, whiteSpace: "nowrap" }}>
                {col.name}
                <Chip
                  label={col.dtype}
                  size="small"
                  variant="outlined"
                  sx={{ ml: 1, height: 18, fontSize: 10 }}
                />
              </TableCell>
            ))}
          </TableRow>
        </TableHead>
        <TableBody>
          {rows.map((row, i) => (
            <TableRow key={i} hover>
              {names.map((name) => (
                <TableCell
                  key={name}
                  sx={{
                    maxWidth: 240,
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                    fontFamily: "'Roboto Mono', monospace",
                    fontSize: 12,
                  }}
                  title={row[name] == null ? "" : String(row[name])}
                >
                  {row[name] == null ? "—" : String(row[name])}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}
