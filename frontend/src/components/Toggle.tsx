interface Props {
  checked: boolean;
  onChange: (value: boolean) => void;
  label: string;
}

export function Toggle({ checked, onChange, label }: Props) {
  return (
    <label className="flex cursor-pointer items-center gap-2 font-mono text-xs text-ink-300">
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`relative h-5 w-9 rounded-full transition ${checked ? "bg-neon-500" : "bg-ink-600"}`}
      >
        <span
          className={`absolute top-0.5 h-4 w-4 rounded-full bg-ink-950 transition-all ${checked ? "left-[18px]" : "left-0.5"}`}
        />
      </button>
      {label}
    </label>
  );
}
