import { MAX_DURATION_MS } from "../useRecorder";

function formatClock(ms) {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000));
  const minutes = String(Math.floor(totalSeconds / 60)).padStart(2, "0");
  const seconds = String(totalSeconds % 60).padStart(2, "0");
  return `${minutes}:${seconds}`;
}

export default function RecordButton({ phase, elapsedMs, onHoldStart, onHoldEnd }) {
  const recording = phase === "recording";

  const handlePointerDown = (event) => {
    if (event.pointerType === "mouse" && event.button !== 0) {
      return;
    }
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    onHoldStart();
  };

  const handlePointerUp = (event) => {
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    onHoldEnd();
  };

  const handlePointerCancel = (event) => {
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    onHoldEnd();
  };

  return (
    <button
      type="button"
      className={recording ? "record-button is-recording" : "record-button"}
      aria-pressed={recording}
      onPointerDown={handlePointerDown}
      onPointerUp={handlePointerUp}
      onPointerCancel={handlePointerCancel}
      onContextMenu={(event) => event.preventDefault()}
    >
      {recording ? `录音中 ${formatClock(elapsedMs)}` : "按住说话"}
      {recording ? (
        <span className="record-limit">最长 {formatClock(MAX_DURATION_MS)}</span>
      ) : null}
    </button>
  );
}
