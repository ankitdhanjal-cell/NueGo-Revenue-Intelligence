import { Link } from 'react-router-dom';
import { useWarnings } from '../api/hooks';
import RangeValue from '../components/RangeValue';
import SectionState from '../components/SectionState';
import { formatDateTime } from '../lib/format';

export default function WarningsPage() {
  const q = useWarnings();
  const items = q.data?.items ?? [];
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-3xl font-semibold">Alerts</h1>
        <p className="mt-1 text-slate-600">
          Services that have not left yet, are selling slower than expected and have no decision.
        </p>
      </div>
      <SectionState
        loading={q.isLoading}
        error={q.error}
        empty={items.length === 0}
        emptyText="Nothing needs attention right now."
      >
        <table className="w-full border-y border-slate-300 bg-white">
          <thead>
            <tr className="border-b border-slate-300">
              {['Service', 'Departs', 'Seats behind', 'Expected by now', 'Seats counted'].map((h) => (
                <th key={h} scope="col" className="px-3 py-2.5">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {items.map((w) => (
              <tr key={w.id} className="border-b border-slate-200 last:border-0">
                <td className="px-3 py-3">
                  <Link className="link" to={`/services/${w.service_id}`}>
                    {w.route_label}
                  </Link>
                </td>
                <td className="px-3 py-3">{formatDateTime(w.departure_at)}</td>
                <td className="px-3 py-3 tabular-nums text-bad">{Math.abs(w.seat_gap)} seats</td>
                <td className="px-3 py-3">
                  <RangeValue range={w.checkpoint} format="seats" />
                </td>
                <td className="px-3 py-3">{formatDateTime(w.raised_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </SectionState>
    </div>
  );
}
