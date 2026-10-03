import type { DetectedItem } from "../types/api";

export function InteractiveInspector({ items }: { items: DetectedItem[] }) {
  return <section aria-label="Interactive inspector"><h2>Inspector</h2><p>{items.length ? `${items.length} findings ready for rendering.` : "Findings will appear here after analysis."}</p></section>;
}
