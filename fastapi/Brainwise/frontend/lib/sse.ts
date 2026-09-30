import type { StreamEvent } from "./types";

export async function* parseSse(
  body: ReadableStream<Uint8Array>,
): AsyncGenerator<StreamEvent> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const frames = buffer.split(/\r?\n\r?\n/);
      buffer = frames.pop() ?? "";

      for (const frame of frames) {
        const parsed = parseFrame(frame);
        if (parsed) yield parsed;
      }
    }

    buffer += decoder.decode();
    if (buffer.trim()) {
      const parsed = parseFrame(buffer);
      if (parsed) yield parsed;
      else throw new Error("Incomplete SSE frame");
    }
  } finally {
    reader.releaseLock();
  }
}

function parseFrame(frame: string): StreamEvent | null {
  if (!frame.trim()) return null;

  let event = "message";
  let dataText = "";
  for (const line of frame.split(/\r?\n/)) {
    if (line.startsWith("event: ")) event = line.slice(7);
    if (line.startsWith("data: ")) dataText += line.slice(6);
  }

  return dataText ? { event, data: JSON.parse(dataText) } : null;
}
