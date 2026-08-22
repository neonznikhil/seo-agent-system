"use client";

import { get, post } from "@/lib/api";

export default function TestE2EPage() {
  const [keyword, setKeyword] = useState("");
  const [logs, setLogs] = useState<string[]>([]);
  const [output, setOutput] = useState<any>(null);
  const [running, setRunning] = useState(false);

  const addLog = (msg: string) => {
    setLogs((prev) => [...prev, msg]);
  };

  const runPipeline = async () => {
    setRunning(true);
    setLogs([]);
    setOutput(null);
    addLog("Starting pipeline for: " + keyword);
    try {
      const websites = await get("/api/websites");
      const websiteId = (Array.isArray(websites) && websites[0]?.id) || "default-website-id";
      const data = await post(`/api/brain/${websiteId}/run-now`, { job_type: "daily_search", keyword });
      setOutput(data);
      addLog("Pipeline completed");
    } catch (e: any) {
      addLog("Error: " + e.message);
    }
    setRunning(false);
  };

  return (
    <div style={{ padding: "2rem", fontFamily: "sans-serif" }}>
      <h1>E2E UI Test</h1>
      <input
        value={keyword}
        onChange={(e) => setKeyword(e.target.value)}
        placeholder="Enter keyword"
        style={{ padding: "0.5rem", marginRight: "1rem" }}
      />
      <button onClick={runPipeline} disabled={running}>
        {running ? "Running..." : "Run Full Agent Pipeline"}
      </button>
      <div style={{ marginTop: "1rem" }}>
        <h2>Live Logs</h2>
        {logs.map((log, i) => (
          <div key={i}>{log}</div>
        ))}
      </div>
      {output && (
        <div style={{ marginTop: "1rem" }}>
          <h2>Output</h2>
          <pre>{JSON.stringify(output, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}
