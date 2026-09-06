export const MIME_CANDIDATES = ["audio/webm;codecs=opus", "audio/webm"];

export function detectAudioMimeType() {
  if (
    typeof MediaRecorder === "undefined" ||
    typeof MediaRecorder.isTypeSupported !== "function"
  ) {
    return null;
  }

  return MIME_CANDIDATES.find((type) => MediaRecorder.isTypeSupported(type)) ?? null;
}

export function fileExtensionForMime(mime) {
  if (mime && mime.includes("webm")) {
    return "webm";
  }
  return "webm";
}
