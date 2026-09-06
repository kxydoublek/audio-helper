import { useEffect, useState } from "react";
import CitySelect from "./components/CitySelect.jsx";
import RecordButton from "./components/RecordButton.jsx";
import RecordingPreview from "./components/RecordingPreview.jsx";
import { useRecorder } from "./useRecorder.js";
import "./App.css";

function App() {
  const [city, setCity] = useState("杭州");
  const { phase, error, result, elapsedMs, startRecording, stopRecording } =
    useRecorder();

  useEffect(() => {
    if (phase !== "recording") {
      return undefined;
    }
    const endHold = () => stopRecording("commit");
    window.addEventListener("pointerup", endHold);
    window.addEventListener("pointercancel", endHold);
    return () => {
      window.removeEventListener("pointerup", endHold);
      window.removeEventListener("pointercancel", endHold);
    };
  }, [phase, stopRecording]);

  return (
    <main className="page">
      <h1>语音约碰面地点</h1>
      <p>按住录音，说出两个人在同一座城市里的位置。本轮只做本地录音，不会上传或找店。</p>
      <CitySelect value={city} onChange={setCity} />
      <RecordButton
        phase={phase}
        elapsedMs={elapsedMs}
        onHoldStart={startRecording}
        onHoldEnd={() => stopRecording("commit")}
      />
      <p className="hint">松开结束。移出按钮后松开、按 Esc 取消，或录满 60 秒，都会结束并释放麦克风。</p>
      {error ? <p className="error">{error}</p> : null}
      <RecordingPreview result={result} />
    </main>
  );
}

export default App;
