import { useCallback, useEffect, useState } from "react";
import {
  Box,
  Breadcrumbs,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  LinearProgress,
  Link,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Typography,
} from "@mui/material";
import FolderIcon from "@mui/icons-material/Folder";
import InsertDriveFileIcon from "@mui/icons-material/InsertDriveFile";
import HomeIcon from "@mui/icons-material/Home";
import ArrowUpwardIcon from "@mui/icons-material/ArrowUpward";
import api from "../api/client.js";

// Browse the local filesystem through the backend and let the user pick a CSV
// file. Returns the chosen absolute path via onSelect().
export default function FileBrowserDialog({ open, onClose, onSelect }) {
  const [currentPath, setCurrentPath] = useState("");
  const [entries, setEntries] = useState({ directories: [], files: [], parent: null, roots: [] });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const browse = useCallback(async (path) => {
    setError("");
    setLoading(true);
    try {
      const data = await api.browseFilesystem(path || undefined);
      setCurrentPath(data.path);
      setEntries(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open) browse("");
  }, [open, browse]);

  const handleNavigate = (path) => browse(path);

  const handleSelectFile = (filePath) => {
    onSelect(filePath);
    onClose();
  };

  // Build breadcrumb segments from the current path.
  const pathSegments = currentPath
    ? currentPath.split("/").filter(Boolean)
    : [];
  // On macOS a path like /Users/aaron → ["Users", "aaron"]; prepend root.
  const breadcrumbs = [
    { label: "/", path: "/" },
    ...pathSegments.map((seg, i) => {
      const full = "/" + pathSegments.slice(0, i + 1).join("/");
      return { label: seg, path: full };
    }),
  ];

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ pb: 1 }}>Browse for a CSV file</DialogTitle>

      <DialogContent dividers>
        {/* Breadcrumb navigation */}
        <Breadcrumbs sx={{ mb: 1.5, "& .MuiBreadcrumbs-li": { fontSize: "0.85rem" } }}>
          {breadcrumbs.map((crumb, i) =>
            i === breadcrumbs.length - 1 ? (
              <Typography key={crumb.path} variant="body2" color="text.primary">
                {crumb.label}
              </Typography>
            ) : (
              <Link
                key={crumb.path}
                component="button"
                underline="hover"
                color="inherit"
                onClick={() => handleNavigate(crumb.path)}
              >
                {crumb.label}
              </Link>
            )
          )}
        </Breadcrumbs>

        {loading && <LinearProgress sx={{ mb: 1 }} />}
        {error && (
          <Typography color="error" variant="body2" sx={{ mb: 1 }}>
            {error}
          </Typography>
        )}

        {/* Quick-jump roots (only shown at top level) */}
        {entries.roots && entries.roots.length > 0 && (
          <Box sx={{ mb: 1.5, display: "flex", gap: 1, flexWrap: "wrap" }}>
            {entries.roots.map((root) => (
              <Button
                key={root}
                size="small"
                variant="outlined"
                startIcon={<HomeIcon />}
                onClick={() => handleNavigate(root)}
              >
                {root === entries.roots[0] ? "Home" : root.split("/").pop() || root}
              </Button>
            ))}
          </Box>
        )}

        {/* Up / parent */}
        {entries.parent && (
          <ListItemButton onClick={() => handleNavigate(entries.parent)} sx={{ borderRadius: 1 }}>
            <ListItemIcon>
              <ArrowUpwardIcon color="action" />
            </ListItemIcon>
            <ListItemText primary=".. (parent folder)" />
          </ListItemButton>
        )}

        <List dense>
          {/* Directories first */}
          {entries.directories.map((d) => (
            <ListItemButton
              key={d.path}
              onClick={() => handleNavigate(d.path)}
              sx={{ borderRadius: 1 }}
            >
              <ListItemIcon>
                <FolderIcon color="primary" />
              </ListItemIcon>
              <ListItemText primary={d.name} />
            </ListItemButton>
          ))}

          {/* CSV files */}
          {entries.files.map((f) => (
            <ListItemButton
              key={f.path}
              onClick={() => handleSelectFile(f.path)}
              sx={{ borderRadius: 1 }}
            >
              <ListItemIcon>
                <InsertDriveFileIcon color="action" />
              </ListItemIcon>
              <ListItemText
                primary={f.name}
                secondary={f.path}
                primaryTypographyProps={{ sx: { fontFamily: "'Roboto Mono', monospace" } }}
                secondaryTypographyProps={{
                  sx: { fontFamily: "'Roboto Mono', monospace", fontSize: "0.7rem", textOverflow: "ellipsis", overflow: "hidden", whiteSpace: "nowrap" },
                }}
              />
              <Button size="small" variant="contained" sx={{ ml: 1, flexShrink: 0 }}>
                Select
              </Button>
            </ListItemButton>
          ))}

          {!loading && entries.directories.length === 0 && entries.files.length === 0 && (
            <Typography variant="body2" color="text.secondary" sx={{ py: 4, textAlign: "center" }}>
              No CSV files in this folder.
            </Typography>
          )}
        </List>
      </DialogContent>

      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
      </DialogActions>
    </Dialog>
  );
}
