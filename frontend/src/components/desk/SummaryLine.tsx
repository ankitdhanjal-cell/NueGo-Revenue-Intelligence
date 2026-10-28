import { useDeskSummary } from '../../api/hooks';
import type { DeskFilters } from '../../api/types';
import SectionState from '../SectionState';

export default function SummaryLine({ filters }: { filters: Pick<DeskFilters, 'window' | 'corridor_id'> }) {
  const q = useDeskSummary(filters);
  const d = q.data;
  const items: [number | undefined, string][] = [
    [d?.services, 'services in this view'],
    [d?.behind_checkpoint, 'selling slowly'],
    [d?.in_loss, "losing money at today's fare"],
    [d?.suggestions_waiting, 'waiting for a decision'],
  ];
  return (
    <SectionState loading={q.isLoading} error={q.error} rows={1}>
      <dl className="grid grid-cols-4 divide-x divide-slate-300 border-y border-slate-300 py-4">
        {items.map(([value, label], i) => (
          <div key={label} className={i === 0 ? 'pr-6' : 'px-6'}>
            <dt className="text-sm text-slate-600">{label}</dt>
            <dd className="font-serif text-3xl font-semibold tabular-nums">{value ?? '—'}</dd>
          </div>
        ))}
      </dl>
    </SectionState>
  );
}
