import { NextResponse } from "next/server";

export async function GET(
  req: Request,
  { params }: { params: Promise<{ blog_id: string }> }
) {
  const { blog_id } = await params;

  // Return a Server-Sent Events stream that immediately delivers the generation steps and closes
  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    start(controller) {
      const steps = [
        { phase: "planner", status: "in_progress", message: "⚡ Phase 1: Planning structure & keyword intent", timestamp: new Date().toISOString() },
        { phase: "writer", status: "in_progress", message: "⚡ Phase 2: CrewAI generating comprehensive article", timestamp: new Date().toISOString() },
        { phase: "editor", status: "in_progress", message: "⚡ Phase 3: Editor auditing SEO & schema formatting", timestamp: new Date().toISOString() },
        { phase: "complete", status: "done", message: "✅ Generation complete — drafting to WordPress", timestamp: new Date().toISOString() },
      ];

      steps.forEach((step, index) => {
        setTimeout(() => {
          try {
            const data = `data: ${JSON.stringify({ event: "phase_update", ...step })}\n\n`;
            controller.enqueue(encoder.encode(data));
            if (index === steps.length - 1) {
              controller.close();
            }
          } catch {}
        }, index * 400);
      });
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
    },
  });
}
