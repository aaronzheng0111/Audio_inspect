/** Fetch and play session audio with clear errors when loading fails. */
export class AudioPlayer {
  constructor() {
    this.audio = new Audio();
    this.objectUrl = null;
  }

  async load(url) {
    this.disposeBlob();
    const response = await fetch(url);
    if (!response.ok) {
      let message = `Could not load audio (HTTP ${response.status})`;
      try {
        const body = await response.json();
        if (body?.error) message = body.error;
      } catch {
        // Response body is not JSON (e.g. HTML error page).
      }
      throw new Error(message);
    }
    const blob = await response.blob();
    if (!blob.size) {
      throw new Error("Audio file is empty.");
    }
    this.objectUrl = URL.createObjectURL(blob);
    this.audio.src = this.objectUrl;
    await this.audio.load();
  }

  async play() {
    await this.audio.play();
  }

  pause() {
    this.audio.pause();
  }

  get paused() {
    return this.audio.paused;
  }

  onEnded(callback) {
    this.audio.onended = callback;
  }

  onPause(callback) {
    this.audio.onpause = callback;
  }

  onPlay(callback) {
    this.audio.onplay = callback;
  }

  dispose() {
    this.pause();
    this.disposeBlob();
    this.audio.src = "";
    this.audio.onended = null;
    this.audio.onpause = null;
    this.audio.onplay = null;
  }

  disposeBlob() {
    if (this.objectUrl) {
      URL.revokeObjectURL(this.objectUrl);
      this.objectUrl = null;
    }
  }
}
