import { useDecisions } from '../../api/hooks';
import { formatDateTime, formatINR, formatSeats } from '../../lib/format';
import SectionState from '../SectionState';

const ACTIONS = { approve: 'Approved', change: 'Changed', reject: 'Rejected', wrong: 'Marked wrong' };

export default function HistorySection({ serviceId }: { serviceId: string }) {
  const q = useDecisions(serviceId);
  const items = q.data?.items ?? [];
  return (
    <section className="card" aria-labelledby="hist-h">
      <h2 id="hist-h" className="mb-2 text-lg font-semibold">
        Past decisions
      </h2>
      <SectionState
        loading={q.isLoading}
        error={q.error}
        empty={items.length === 0}
        emptyText="No decisions recorded for this service yet."
      >
        <table className="w-full">
          <thead>
            <tr>
              {['Who', 'When', 'Action', 'Fare', 'Reason', 'Engine fare', 'Our fare', 'Outcome'].map((h) => (
                <th key={h} scope="col" className="px-2 py-1">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {items.map((d) => (
              <tr key={d.id} className="border-t border-slate-100 align-top">
                <td className="px-2 py-1">{d.user}</td>
                <td className="px-2 py-1">{formatDateTime(d.at)}</td>
                <td className="px-2 py-1">{ACTIONS[d.action]}</td>
                <td className="px-2 py-1">{formatINR(d.fare)}</td>
                <td className="px-2 py-1">{[d.category, d.reason].filter(Boolean).join(': ') || '—'}</td>
                <td className="px-2 py-1">{formatINR(d.engine_fare)}</td>
                <td className="px-2 py-1">{formatINR(d.our_fare)}</td>
                <td className="px-2 py-1">
                  {d.outcome
                    ? `${formatSeats(d.outcome.final_seats)} seats, ${formatINR(d.outcome.revenue)}`
                    : 'Not in the data'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </SectionState>
    </section>
  );
}
