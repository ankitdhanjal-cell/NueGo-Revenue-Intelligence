import { useSuggestion, useWhatIf } from '../../api/hooks';
import { RULE_LABELS } from '../../lib/labels';
import Money from '../Money';
import RangeValue from '../RangeValue';
import SectionState from '../SectionState';

export default function WhatIfSection({ serviceId }: { serviceId: string }) {
  const q = useWhatIf(serviceId);
  const s = useSuggestion(serviceId).data;
  const rows = q.data?.rows ?? [];
  const engine = s?.engine_fare ?? null;
  const nearest =
    engine == null || rows.length === 0
      ? null
      : rows.reduce((a, b) => (Math.abs(b.fare - engine) < Math.abs(a.fare - engine) ? b : a)).fare;
  return (
    <section className="card" aria-labelledby="wi-h">
      <h2 id="wi-h" className="mb-2 text-lg font-semibold">
        Every allowed fare
      </h2>
      {q.data?.flags.price_response_not_reliable && (
        <p className="mb-2 text-sm text-slate-600">
          The seat model shows more seats at higher fares in this data, so read the seat and revenue columns
          as model output, not as a price-response curve.
        </p>
      )}
      <SectionState
        loading={q.isLoading}
        error={q.error}
        empty={rows.length === 0}
        emptyText="No what-if data for this service."
        rows={5}
      >
        <div className="max-h-96 overflow-y-auto rounded border border-slate-200">
          <table className="w-full">
            <thead className="sticky top-0 bg-slate-50">
              <tr>
                {['Fare', 'Expected seats', 'Revenue', 'Margin', 'Rules'].map((h) => (
                  <th key={h} scope="col" className="px-3 py-2">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const blocked = r.blocked_by.length > 0;
                const isSuggested = s?.suggested_fare === r.fare;
                const isCurrent = nearest === r.fare;
                return (
                  <tr
                    key={r.fare}
                    className={`border-t border-slate-100 ${blocked ? 'bg-slate-50 text-slate-400' : ''} ${isSuggested ? 'bg-emerald-50 font-medium' : ''} ${isCurrent ? 'outline outline-1 -outline-offset-1 outline-slate-400' : ''}`}
                  >
                    <td className="px-3 py-1.5">
                      <Money value={r.fare} />
                      {isCurrent && (
                        <span className="ml-2 rounded bg-slate-200 px-1 text-[10px] font-semibold text-slate-700">
                          Current
                        </span>
                      )}
                      {isSuggested && (
                        <span className="ml-2 rounded bg-emerald-200 px-1 text-[10px] font-semibold text-emerald-900">
                          Suggested
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-1.5">
                      <RangeValue range={r.seats} format="seats" />
                    </td>
                    <td className="px-3 py-1.5">
                      <RangeValue range={r.revenue} format="inr" />
                    </td>
                    <td className="px-3 py-1.5">
                      <RangeValue range={r.margin} format="inr" missing="Cost missing" />
                    </td>
                    <td className="px-3 py-1.5 text-xs">
                      {blocked
                        ? `Blocked: ${r.blocked_by.map((c) => RULE_LABELS[c] ?? c).join(', ')}`
                        : 'Allowed'}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </SectionState>
    </section>
  );
}
