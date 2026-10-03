"use client";

import type { ContentType } from "../types/api";

export function UploadZone({ contentType, onContentTypeChange }: { contentType: ContentType; onContentTypeChange: (value: ContentType) => void }) {
  return <section aria-label="Upload content"><h2>Inspect content</h2><div role="tablist"><button onClick={() => onContentTypeChange("text")} aria-selected={contentType === "text"}>Text</button><button onClick={() => onContentTypeChange("image")} aria-selected={contentType === "image"}>Image</button></div><p>Skeleton input area — feature track pending.</p></section>;
}
