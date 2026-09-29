import { proxyJson } from "../_lib/proxy";

// Article generation is owned by the backend (CrewAI/NVIDIA pipeline). The old
// handler fell back to an in-memory stub that invented article content and
// fabricated a "generated" success whenever the backend call failed. Now the
// real result (or honest failure) is passed through unchanged.
export async function POST(req: Request) {
  return proxyJson("/api/generate", req, 300000);
}
