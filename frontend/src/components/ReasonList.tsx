import type { Reason } from '../api/types';

/** Reasons exactly as the API sends them. The text is never rewritten here. */
export default function ReasonList({ reasons }: { reasons: Reason[] }) {
  if (reasons.length === 0) return null;
  return (
    <ul className="space-y-1">
      {reasons.map((r) => (
        <li key={r.code} className="flex gap-2">
          <span className="mt-0.5 shrink-0 rounded bg-slate-100 px-1.5 text-[10px] font-semibold uppercase tracking-wide text-slate-600">
            {r.code.replace('_', ' ').toLowerCase()}
          </span>
          <span>{r.text}</span>
        </li>
      ))}
    </ul>
  );
}
