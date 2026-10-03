"use client";

import { useState } from "react";
import { ControlPanel } from "../components/ControlPanel";
import { ExportBar } from "../components/ExportBar";
import { InteractiveInspector } from "../components/InteractiveInspector";
import { SummaryBadge } from "../components/SummaryBadge";
import { UploadZone } from "../components/UploadZone";
import type { Action, ContentType, DetectedItem } from "../types/api";

export default function Home() {
  const [contentType, setContentType] = useState<ContentType>("text");
  const [items, setItems] = useState<DetectedItem[]>([]);
  return <main style={{ maxWidth: 960, margin: "0 auto", padding: 32 }}>
    <header><p>PS-06 · PERSONAL DATA PRIVACY SHIELD</p><h1>Privacy Shield</h1><p>Skeleton UI — shared contract locked, feature tracks pending.</p></header>
    <UploadZone contentType={contentType} onContentTypeChange={setContentType} />
    <SummaryBadge summary={null} />
    <InteractiveInspector items={items} />
    <ControlPanel items={items} onActionChange={(id: string, action: Action) => setItems((current) => current.map((item) => item.id === id ? { ...item, action } : item))} />
    <ExportBar />
  </main>;
}
