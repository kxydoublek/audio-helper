import { fileExtensionForMime } from "../audioFormat";

function formatDuration(ms) {
  const seconds = ms / 1000;
  return `${seconds.toFixed(1)} 秒`;
}

function formatSize(bytes) {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  return `${(bytes / 1024).toFixed(1)} KB`;
}

export default function RecordingPreview({ result }) {
  if (!result) {
    return null;
  }

  const extension = fileExtensionForMime(result.mime);
  const filename = `meetup-recording.${extension}`;

  return (
    <section className="recording-preview">
      <h2>本地试听</h2>
      <audio controls src={result.url} preload="metadata">
        当前浏览器无法播放这段录音。
      </audio>
      <p className="meta">
        格式 {result.mime} · 时长 {formatDuration(result.durationMs)} · 大小{" "}
        {formatSize(result.sizeBytes)}
      </p>
      <a className="download" href={result.url} download={filename}>
        下载录音文件
      </a>
    </section>
  );
}
