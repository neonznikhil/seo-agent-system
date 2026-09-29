import { proxyJson } from "../../_lib/proxy";

// Crew generation is owned by the backend (3-agent CrewAI pipeline). The old
// handler fell back to an in-memory stub that fabricated article content and a
// "generated" success. Pass the real result (or honest failure) through.
export async function POST(req: Request) {
  return proxyJson("/api/crew/generate", req, 300000);
}
