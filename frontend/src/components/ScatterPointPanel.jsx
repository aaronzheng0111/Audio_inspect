import { useEffect, useRef, useState } from "react";
import {
  Alert,
  Box,
  Divider,
  IconButton,
  Paper,
  Stack,
  Typography,
} from "@mui/material";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import PauseIcon from "@mui/icons-material/Pause";
import { AudioPlayer } from "../models/AudioPlayer.js";

/** Metadata and audio playback for one selected scatter point. */
export default function ScatterPointPanel({ point }) {
  const [playing, setPlaying] = useState(false);
  const [audioError, setAudioError] = useState("");
  const [loadingAudio, setLoadingAudio] = useState(false);
  const playerRef = useRef(null);

  if (!playerRef.current) {
    playerRef.current = new AudioPlayer();
  }

  useEffect(() => {
    const player = playerRef.current;
    setPlaying(false);
    setAudioError("");

    if (!point?.audioUrl()) {
      player.dispose();
      return undefined;
    }

    let cancelled = false;
    setLoadingAudio(true);
    player
      .load(point.audioUrl())
      .then(() => {
        if (!cancelled) setLoadingAudio(false);
      })
      .catch((error) => {
        if (!cancelled) {
          setLoadingAudio(false);
          setAudioError(error.message || "Could not load audio.");
        }
      });

    player.onEnded(() => setPlaying(false));
    player.onPause(() => setPlaying(false));
    player.onPlay(() => setPlaying(true));

    return () => {
      cancelled = true;
      player.dispose();
    };
  }, [point]);

  useEffect(
    () => () => {
      playerRef.current?.dispose();
    },
    []
  );

  const togglePlayback = async () => {
    const player = playerRef.current;
    if (!player || !point?.audioUrl() || loadingAudio || audioError) return;
    if (!player.paused) {
      player.pause();
      setPlaying(false);
      return;
    }
    try {
      setAudioError("");
      await player.play();
      setPlaying(true);
    } catch (error) {
      setPlaying(false);
      setAudioError(error.message || "Playback was blocked by the browser.");
    }
  };

  if (!point) {
    return (
      <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
        <Typography variant="body2" color="text.secondary">
          Switch to scatter and click a point to view metadata and play its audio.
        </Typography>
      </Paper>
    );
  }

  const sentence = point.sentenceText();
  const detailEntries = point.metadataEntries().filter((entry) => !entry.isSentence || !sentence);

  return (
    <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
      <Stack spacing={1.5}>
        <Stack direction="row" alignItems="flex-start" spacing={1}>
          <IconButton
            color="primary"
            onClick={togglePlayback}
            disabled={!point.audioUrl() || loadingAudio || Boolean(audioError)}
            aria-label={playing ? "Pause audio" : "Play audio"}
            sx={{ mt: 0.25 }}
          >
            {playing ? <PauseIcon /> : <PlayArrowIcon />}
          </IconButton>
          <Box sx={{ flex: 1 }}>
            <Typography variant="subtitle2">
              Row {point.rowIndex + 1} · {point.dataset.column} = {point.metricValue}
            </Typography>
            {loadingAudio && (
              <Typography variant="caption" color="text.secondary">
                Loading audio…
              </Typography>
            )}
          </Box>
        </Stack>

        {audioError && <Alert severity="error">{audioError}</Alert>}

        {sentence && (
          <Box>
            <Typography variant="caption" color="text.secondary" display="block">
              Sentence
            </Typography>
            <Typography variant="body1" sx={{ wordBreak: "break-word", lineHeight: 1.5 }}>
              {sentence}
            </Typography>
          </Box>
        )}

        <Divider />
        <Stack spacing={0.75}>
          {detailEntries.map(({ column, label, value, isPath }) => (
            <Box key={column}>
              <Typography variant="caption" color="text.secondary" display="block">
                {label}
              </Typography>
              <Typography
                variant="body2"
                sx={{
                  wordBreak: "break-word",
                  fontFamily: isPath ? "'Roboto Mono', monospace" : "inherit",
                }}
              >
                {value}
              </Typography>
            </Box>
          ))}
        </Stack>
      </Stack>
    </Paper>
  );
}
