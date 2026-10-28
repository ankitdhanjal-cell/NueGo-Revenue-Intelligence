import type { Status } from '../api/types';

const STYLE: Record<Status, { label: string; dot: string; text: string }> = {
  behind: { label: 'Selling slowly', dot: 'bg-bad', text: 'text-bad' },
  on_pace: { label: 'On track', dot: 'bg-slate-400', text: 'text-slate-700' },
  ahead: { label: 'Selling well', dot: 'bg-good', text: 'text-good' },
};

/** A dot and a word: the word carries the meaning, the colour only helps. */
export default function StatusChip({ status }: { status: Status | null }) {
  if (!status) return <span className="text-slate-400">No forecast</span>;
  const s = STYLE[status];
  return (
    <span className={`inline-flex items-center gap-1.5 font-medium ${s.text}`}>
      <span aria-hidden="true" className={`h-2 w-2 rounded-full ${s.dot}`} />
      {s.label}
    </span>
  );
}
