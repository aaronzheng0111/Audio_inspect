import {
  Card,
  CardContent,
  Checkbox,
  Chip,
  FormControlLabel,
  Grid,
  Stack,
  Tooltip,
  Typography,
} from "@mui/material";
import InfoOutlinedIcon from "@mui/icons-material/InfoOutlined";

// Grid of selectable acoustic metrics with an "ALL" master toggle.
// Approximate metrics are visually flagged. Used on Mapping & Metric pages
// (Task 3 & 4).
export default function MetricSelector({ metrics, selected, onChange }) {
  const allKeys = metrics.map((m) => m.key);
  const allSelected = allKeys.length > 0 && selected.length === allKeys.length;

  const toggle = (key) => {
    onChange(
      selected.includes(key)
        ? selected.filter((k) => k !== key)
        : [...selected, key]
    );
  };

  const toggleAll = () => {
    onChange(allSelected ? [] : allKeys);
  };

  return (
    <Stack spacing={2}>
      <FormControlLabel
        control={<Checkbox checked={allSelected} onChange={toggleAll} />}
        label={<Typography fontWeight={600}>ALL metrics</Typography>}
      />
      <Grid container spacing={2}>
        {metrics.map((metric) => {
          const isSelected = selected.includes(metric.key);
          return (
            <Grid item xs={12} sm={6} md={4} key={metric.key}>
              <Card
                variant="outlined"
                onClick={() => toggle(metric.key)}
                sx={{
                  cursor: "pointer",
                  borderColor: isSelected ? "primary.main" : "divider",
                  bgcolor: isSelected ? "rgba(25,118,210,0.06)" : "background.paper",
                  transition: "all .15s",
                }}
              >
                <CardContent sx={{ pb: "12px !important" }}>
                  <Stack direction="row" alignItems="center" spacing={1}>
                    <Checkbox checked={isSelected} size="small" sx={{ p: 0 }} />
                    <Typography fontWeight={600}>{metric.label}</Typography>
                    {metric.approximate && (
                      <Tooltip title="Approximate implementation; interpret with care.">
                        <Chip
                          icon={<InfoOutlinedIcon />}
                          label="approx"
                          size="small"
                          color="warning"
                          variant="outlined"
                          sx={{ height: 20 }}
                        />
                      </Tooltip>
                    )}
                  </Stack>
                  <Typography variant="caption" color="text.secondary">
                    {metric.description}
                  </Typography>
                  <Typography
                    variant="caption"
                    display="block"
                    color="text.secondary"
                    sx={{ mt: 0.5 }}
                  >
                    unit: {metric.unit || "—"} · cost: {metric.cost}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
          );
        })}
      </Grid>
    </Stack>
  );
}
