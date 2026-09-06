import { useCallback, useEffect, useRef, useState } from "react";
import { detectAudioMimeType } from "./audioFormat";

export const MIN_DURATION_MS = 1000;
export const MAX_DURATION_MS = 60_000;
export const MAX_BYTES = 5 * 1024 * 1024;

const UNSUPPORTED_MESSAGE =
  "当前浏览器无法录制 WebM/Opus，请更换 Chrome 或 Edge 后重试。";

function stopStream(stream) {
  if (!stream) {
    return;
  }
  stream.getTracks().forEach((track) => track.stop());
}

function createRecorder(stream, mime) {
  try {
    return new MediaRecorder(stream, { mimeType: mime });
  } catch {
    return new MediaRecorder(stream);
  }
}

export function useRecorder() {
  const [phase, setPhase] = useState("idle");
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const [elapsedMs, setElapsedMs] = useState(0);

  const sessionRef = useRef(0);
  const recorderRef = useRef(null);
  const streamRef = useRef(null);
  const chunksRef = useRef([]);
  const startedAtRef = useRef(0);
  const mimeRef = useRef(null);
  const maxTimerRef = useRef(null);
  const tickRef = useRef(null);
  const finalizeModeRef = useRef("commit");
  const resultRef = useRef(null);
  const resultUrlRef = useRef(null);
  const stoppingRef = useRef(false);
  const startingRef = useRef(false);

  const setKeptResult = useCallback((next) => {
    resultRef.current = next;
    setResult(next);
  }, []);

  const restoreAfterAbort = useCallback(() => {
    setElapsedMs(0);
    setPhase(resultRef.current ? "ready" : "idle");
  }, []);

  const clearTimers = useCallback(() => {
    if (maxTimerRef.current !== null) {
      window.clearTimeout(maxTimerRef.current);
      maxTimerRef.current = null;
    }
    if (tickRef.current !== null) {
      window.clearInterval(tickRef.current);
      tickRef.current = null;
    }
  }, []);

  const releaseMic = useCallback(() => {
    stopStream(streamRef.current);
    streamRef.current = null;
  }, []);

  const applyBlob = useCallback(
    (blob, durationMs, mime) => {
      if (durationMs < MIN_DURATION_MS) {
        setError("请将录音控制在 1 到 60 秒。");
        restoreAfterAbort();
        return;
      }
      const storedDuration = Math.min(durationMs, MAX_DURATION_MS);
      if (!blob || blob.size === 0) {
        setError("录制失败，请重试。");
        restoreAfterAbort();
        return;
      }
      if (blob.size > MAX_BYTES) {
        setError("录音文件不能超过 5MB，请缩短录音后重试。");
        restoreAfterAbort();
        return;
      }

      if (resultUrlRef.current) {
        URL.revokeObjectURL(resultUrlRef.current);
      }
      const url = URL.createObjectURL(blob);
      resultUrlRef.current = url;
      setError(null);
      setKeptResult({
        blob,
        url,
        mime,
        durationMs: storedDuration,
        sizeBytes: blob.size,
      });
      setElapsedMs(0);
      setPhase("ready");
    },
    [restoreAfterAbort, setKeptResult],
  );

  const stopRecording = useCallback(
    (mode) => {
      if (stoppingRef.current) {
        if (mode === "discard") {
          finalizeModeRef.current = "discard";
        }
        return;
      }

      const recorder = recorderRef.current;
      if (!recorder || recorder.state === "inactive") {
        finalizeModeRef.current = mode;
        sessionRef.current += 1;
        startingRef.current = false;
        clearTimers();
        releaseMic();
        if (mode === "discard") {
          setError(null);
        }
        restoreAfterAbort();
        return;
      }

      stoppingRef.current = true;
      finalizeModeRef.current = mode;
      sessionRef.current += 1;
      startingRef.current = false;
      clearTimers();
      recorderRef.current = null;
      try {
        recorder.stop();
      } catch (err) {
        console.error("[recorder] stop failed", err);
        stoppingRef.current = false;
        releaseMic();
        setError("录制失败，请重试。");
        restoreAfterAbort();
      }
    },
    [clearTimers, releaseMic, restoreAfterAbort],
  );

  const startRecording = useCallback(async () => {
    if (
      startingRef.current ||
      stoppingRef.current ||
      (recorderRef.current && recorderRef.current.state !== "inactive")
    ) {
      return;
    }

    setError(null);

    const mime = detectAudioMimeType();
    if (!mime) {
      setError(UNSUPPORTED_MESSAGE);
      return;
    }

    startingRef.current = true;
    sessionRef.current += 1;
    const session = sessionRef.current;
    finalizeModeRef.current = "commit";
    chunksRef.current = [];
    mimeRef.current = mime;
    setElapsedMs(0);

    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (err) {
      startingRef.current = false;
      if (session !== sessionRef.current) {
        return;
      }
      console.error("[recorder] getUserMedia failed", err);
      const name = err && err.name;
      if (name === "NotAllowedError" || name === "PermissionDeniedError") {
        setError("无法使用麦克风，请在浏览器中允许麦克风权限后重试。");
      } else if (name === "NotFoundError" || name === "DevicesNotFoundError") {
        setError("没有找到麦克风，请接好设备后重试。");
      } else if (name === "NotReadableError" || name === "TrackStartError") {
        setError("无法访问麦克风，可能被其他应用占用，请关闭后重试。");
      } else {
        setError("录制失败，请重试。");
      }
      restoreAfterAbort();
      return;
    }

    if (session !== sessionRef.current) {
      stopStream(stream);
      startingRef.current = false;
      return;
    }

    streamRef.current = stream;

    let recorder;
    try {
      recorder = createRecorder(stream, mime);
    } catch (err) {
      console.error("[recorder] MediaRecorder failed", err);
      startingRef.current = false;
      stopStream(stream);
      streamRef.current = null;
      setError("录制失败，请重试。");
      restoreAfterAbort();
      return;
    }

    recorderRef.current = recorder;
    recorder.ondataavailable = (event) => {
      if (event.data && event.data.size > 0) {
        chunksRef.current.push(event.data);
      }
    };
    recorder.onerror = (event) => {
      console.error("[recorder] MediaRecorder error", event);
      stoppingRef.current = false;
      startingRef.current = false;
      sessionRef.current += 1;
      clearTimers();
      releaseMic();
      recorderRef.current = null;
      setError("录制失败，请重试。");
      restoreAfterAbort();
    };
    recorder.onstop = () => {
      const durationMs = startedAtRef.current
        ? Date.now() - startedAtRef.current
        : 0;
      const usedMime = recorder.mimeType || mimeRef.current || mime;
      const blob = new Blob(chunksRef.current, { type: usedMime || "audio/webm" });
      chunksRef.current = [];
      stoppingRef.current = false;
      startingRef.current = false;
      releaseMic();
      startedAtRef.current = 0;

      if (finalizeModeRef.current === "discard") {
        setError(null);
        restoreAfterAbort();
        return;
      }
      applyBlob(blob, durationMs, usedMime || "audio/webm");
    };

    try {
      recorder.start(250);
    } catch (err) {
      console.error("[recorder] start failed", err);
      startingRef.current = false;
      recorderRef.current = null;
      releaseMic();
      setError("录制失败，请重试。");
      restoreAfterAbort();
      return;
    }

    startedAtRef.current = Date.now();
    startingRef.current = false;
    setPhase("recording");

    tickRef.current = window.setInterval(() => {
      if (!startedAtRef.current) {
        return;
      }
      setElapsedMs(Math.min(Date.now() - startedAtRef.current, MAX_DURATION_MS));
    }, 200);

    maxTimerRef.current = window.setTimeout(() => {
      stopRecording("commit");
    }, MAX_DURATION_MS);
  }, [applyBlob, clearTimers, releaseMic, restoreAfterAbort, stopRecording]);

  useEffect(() => {
    const onKeyDown = (event) => {
      if (event.key === "Escape") {
        stopRecording("discard");
      }
    };
    const onVisibility = () => {
      if (document.hidden) {
        stopRecording("commit");
      }
    };

    window.addEventListener("keydown", onKeyDown);
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [stopRecording]);

  useEffect(() => {
    return () => {
      sessionRef.current += 1;
      startingRef.current = false;
      stoppingRef.current = false;
      clearTimers();
      if (recorderRef.current && recorderRef.current.state !== "inactive") {
        try {
          recorderRef.current.stop();
        } catch {
          /* already stopped */
        }
      }
      recorderRef.current = null;
      releaseMic();
      if (resultUrlRef.current) {
        URL.revokeObjectURL(resultUrlRef.current);
      }
    };
  }, [clearTimers, releaseMic]);

  return {
    phase,
    error,
    result,
    elapsedMs,
    startRecording,
    stopRecording,
  };
}
