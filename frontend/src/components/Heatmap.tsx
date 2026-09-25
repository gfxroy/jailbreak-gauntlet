import type { HeatmapCell } from "../api/types";
import { heatColor, pct, techniqueLabel } from "../lib/format";

interface Props {
  cells: HeatmapCell[];
  techniques: string[];
  levels: number[];
}

/** Technique x level grid; colour = share of attempts that extracted information. */
export function Heatmap({ cells, techniques, levels }: Props) {
  const lookup = new Map(cells.map((c) => [`${c.technique}:${c.level}`, c]));
  if (techniques.length === 0) {
    return <p className="font-mono text-sm text-ink-400">No attempts recorded yet.</p>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-separate border-spacing-1 font-mono text-[11px]">
        <thead>
          <tr>
            <th className="text-left font-normal text-ink-400">technique ↓ / level →</th>
            {levels.map((l) => (
              <th key={l} className="w-14 font-normal text-ink-300">
                L{l}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {techniques.map((t) => (
            <tr key={t}>
              <td className="whitespace-nowrap pr-2 text-ink-200">{techniqueLabel(t)}</td>
              {levels.map((l) => {
                const cell = lookup.get(`${t}:${l}`);
                const attempts = cell?.attempts ?? 0;
                const rate = cell?.bypass_rate ?? 0;
                return (
                  <td
                    key={l}
                    title={`${techniqueLabel(t)} on level ${l}: ${attempts} attempts, ${pct(rate)} extracted info`}
                    className="h-8 rounded text-center"
                    style={{
                      background: heatColor(rate, attempts),
                      color: rate > 0.3 && attempts ? "#05070a" : "#b8c4d4",
                    }}
                    data-testid={`cell-${t}-${l}`}
                  >
                    {attempts ? pct(rate) : "·"}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <div className="mt-3 flex items-center gap-2 font-mono text-[10px] text-ink-400">
        <span>0%</span>
        <span
          className="h-2 w-40 rounded"
          style={{ background: `linear-gradient(90deg, ${heatColor(0, 1)}, ${heatColor(0.5, 1)}, ${heatColor(1, 1)})` }}
        />
        <span>100% of attempts leaked full or partial info</span>
      </div>
    </div>
  );
}
