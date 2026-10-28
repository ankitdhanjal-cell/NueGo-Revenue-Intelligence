import type { FlagName, Flags } from '../api/types';
import { FLAG_LABELS } from '../lib/labels';

const SHOWN: FlagName[] = ['cost_missing', 'no_history', 'low_confidence', 'rival_missing', 'floor_missing'];

export default function FlagBadges({ flags }: { flags: Flags | undefined }) {
  const on = SHOWN.filter((f) => flags?.[f]);
  if (on.length === 0) return null;
  return (
    <span className="inline-flex flex-wrap gap-x-3 gap-y-1">
      {on.map((f) => (
        <span key={f} className="text-xs font-medium text-ochre-700">
          ⚑ {FLAG_LABELS[f]}
        </span>
      ))}
    </span>
  );
}
