// Next.js API route to proxy chat requests to the FastAPI backend.
// The default Next.js rewrite proxy has a ~30s timeout which is too
// short for LLM chat calls (40-60s). This route has no such limit.

export const maxDuration = 120; // Vercel/Next.js max execution time in seconds

export async function POST(
  request: Request,
  { params }: { params: { sessionId: string } }
) {
  const body = await request.json();

  try {
    const backendUrl = `http://localhost:8000/api/builder/${params.sessionId}/chat`;

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 120_000);

    const res = await fetch(backendUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!res.ok) {
      const errorText = await res.text();
      return new Response(errorText, {
        status: res.status,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    const data = await res.json();
    return Response.json(data);
  } catch (err: any) {
    if (err.name === 'AbortError') {
      return Response.json(
        { detail: 'Backend request timed out after 120s' },
        { status: 504 }
      );
    }
    return Response.json(
      { detail: err.message || 'Internal proxy error' },
      { status: 502 }
    );
  }
}
