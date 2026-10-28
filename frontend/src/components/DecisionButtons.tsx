import { useState } from 'react';
import type { DecisionAction, Suggestion } from '../api/types';
import DecisionDialog from './DecisionDialog';

const BUTTONS: { action: DecisionAction; label: string; cls: string }[] = [
  { action: 'approve', label: 'Approve', cls: 'btn-primary' },
  { action: 'change', label: 'Change fare', cls: '' },
  { action: 'reject', label: 'Reject', cls: 'btn-danger' },
  { action: 'wrong', label: 'Something looks wrong', cls: '' },
];

/** The four decision buttons. A decision is only recorded here; it is never sent to a pricing system. */
export default function DecisionButtons({ suggestion }: { suggestion: Suggestion }) {
  const [open, setOpen] = useState<DecisionAction | null>(null);
  if (suggestion.suggested_fare == null) return null;
  return (
    <div>
      <div className="flex flex-wrap gap-2">
        {BUTTONS.map((b) => (
          <button key={b.action} type="button" className={`btn ${b.cls}`} onClick={() => setOpen(b.action)}>
            {b.label}
          </button>
        ))}
      </div>
      {open && <DecisionDialog action={open} suggestion={suggestion} onClose={() => setOpen(null)} />}
    </div>
  );
}
