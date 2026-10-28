import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useWarnings } from '../api/hooks';
import RangeValue from '../components/RangeValue';
import SectionState from '../components/SectionState';
import { useDefaultAlertOwner } from '../lib/alerts';
import { formatDateTime } from '../lib/format';
import { useUser } from '../lib/user';

export default function WarningsPage() {
  const { user, users } = useUser();
  const defaultOwner = useDefaultAlertOwner();
  const [picked, setPicked] = useState<string | null>(null);
  const who = picked ?? defaultOwner;
  const q = useWarnings(who || undefined);
  const items = q.data?.items ?? [];
  const nameOf = (id: string | null) => users.find((u) => u.id === id)?.name ?? 'No owner yet';
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-3xl font-semibold">Alerts</h1>
        <p className="mt-1 text-slate-600">
          Services that have not left yet, are selling slower than expected and have no decision.
        </p>
        <label className="mt-3 flex items-center gap-2">
          <span className="label mb-0">Show alerts for</span>
          <select className="input w-auto" value={who} onChange={(e) => setPicked(e.target.value)}>
            <option value="">Everyone</option>
            {users.map((u) => (
              <option key={u.id} value={u.id}>
                {u.id === user.id ? `${u.name} (me)` : u.name}
              </option>
            ))}
          </select>
        </label>
      </div>
      <SectionState
        loading={q.isLoading}
        error={q.error}
        empty={items.length === 0}
        emptyText={
          who ? 'Nothing needs attention on this person’s routes.' : 'Nothing needs attention right now.'
        }
      >
        <table className="w-full border-y border-slate-300 bg-white">
          <thead>
            <tr className="border-b border-slate-300">
              {['Service', 'Owner', 'Departs', 'Seats behind', 'Expected by now', 'Seats counted'].map(
                (h) => (
                  <th key={h} scope="col" className="px-3 py-2.5">
                    {h}
                  </th>
                ),
              )}
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
                <td className="px-3 py-3">{nameOf(w.owner_id)}</td>
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
