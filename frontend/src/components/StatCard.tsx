interface Props {
  label: string;
  value: string | number;
  sub?: string;
  accent?: string;
}

export function StatCard({ label, value, sub, accent = "text-ink-100" }: Props) {
  return (
    <div className="panel p-4">
      <p className="panel-title">{label}</p>
      <p className={`mt-2 font-mono text-3xl font-semibold ${accent}`}>{value}</p>
      {sub && <p className="mt-1 text-xs text-ink-400">{sub}</p>}
    </div>
  );
}
