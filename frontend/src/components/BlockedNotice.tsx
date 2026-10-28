import type { Suggestion } from '../api/types';
import { formatINR } from '../lib/format';
import { BLOCKED_LABELS, RULE_LABELS } from '../lib/labels';

/** Why there is no suggestion. Plain statements built from the API's blocked_reason and numbers. */
export default function BlockedNotice({ suggestion }: { suggestion: Suggestion }) {
  const code = suggestion.blocked_reason ?? '';
  const d = suggestion.blocked_detail;
  return (
    <div className="rounded border border-ochre-100 bg-ochre-50 p-3 text-ochre-900">
      <p className="font-medium">No suggestion. {BLOCKED_LABELS[code] ?? 'No safe fare could be found.'}</p>
      {code === 'NO_ALLOWED_FARE' && d && (
        <ul className="mt-1 list-disc pl-5 text-xs">
          <li>
            Cost floor {formatINR(d.floor_value)}; highest fare the other rules allow{' '}
            {d.highest_fare_allowed_ignoring_floor == null
              ? 'none'
              : formatINR(d.highest_fare_allowed_ignoring_floor)}
            .
          </li>
          {Object.entries(d.fare_steps_broken_by_rule).map(([rule, n]) => (
            <li key={rule}>
              {RULE_LABELS[rule] ?? rule}: {n} fare steps
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
