import type { FlagName, Flags } from '../api/types';
import { FLAG_LABELS } from '../lib/labels';

export default function FlagBadges({ flags }: { flags: Flags | undefined }) {
  const on = (Object.keys(FLAG_LABELS) as FlagName[]).filter((f) => flags?.[f]);
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
