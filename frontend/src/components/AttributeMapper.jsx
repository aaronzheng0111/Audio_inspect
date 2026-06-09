import {
  FormControl,
  Grid,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  Typography,
} from "@mui/material";

// Lets the user bind their actual CSV columns to the canonical required names
// (audio_name_id / text / audio_path). Used on the Mapping page (Task 3).
const REQUIRED = [
  { key: "audio_name_id", label: "Audio name / id", required: false },
  { key: "text", label: "Text / transcript", required: false },
  { key: "audio_path", label: "Audio path", required: true },
];

export default function AttributeMapper({ columns, mapping, onChange }) {
  const handleSelect = (canonical, value) => {
    onChange({ ...mapping, [canonical]: value });
  };

  return (
    <Stack spacing={2}>
      <Typography variant="body2" color="text.secondary">
        Match the required attributes to columns in your CSV. Column names that
        differ from the standard can be mapped here. <b>audio_path</b> is
        required so the backend can read the audio files.
      </Typography>
      <Grid container spacing={2}>
        {REQUIRED.map((field) => (
          <Grid item xs={12} sm={4} key={field.key}>
            <FormControl fullWidth size="small">
              <InputLabel>
                {field.label}
                {field.required ? " *" : ""}
              </InputLabel>
              <Select
                label={field.label + (field.required ? " *" : "")}
                value={mapping[field.key] || ""}
                onChange={(e) => handleSelect(field.key, e.target.value)}
                error={field.required && !mapping[field.key]}
              >
                <MenuItem value="">
                  <em>— none —</em>
                </MenuItem>
                {columns.map((col) => (
                  <MenuItem key={col.name} value={col.name}>
                    {col.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
        ))}
      </Grid>
    </Stack>
  );
}
