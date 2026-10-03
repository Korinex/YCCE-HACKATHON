export function ExportBar({ disabled = true, onExport }: { disabled?: boolean; onExport?: () => void }) {
  return <button disabled={disabled} onClick={onExport}>Generate protected output</button>;
}
