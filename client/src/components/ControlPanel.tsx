import type { Action, DetectedItem } from "../types/api";

export function ControlPanel({ items, onActionChange }: { items: DetectedItem[]; onActionChange: (id: string, action: Action) => void }) {
  return <section aria-label="Protection controls"><h2>Protection controls</h2>{items.map((item) => <div key={item.id}><span>{item.type}</span>{(["MASK", "REMOVE", "KEEP"] as Action[]).map((action) => <button key={action} onClick={() => onActionChange(item.id, action)}>{action}</button>)}</div>)}</section>;
}
