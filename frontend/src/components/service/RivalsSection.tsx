import { useRivals } from '../../api/hooks';
import { formatTime } from '../../lib/format';
import FlagBadges from '../FlagBadges';
import Money from '../Money';
import SectionState from '../SectionState';

export default function RivalsSection({ serviceId }: { serviceId: string }) {
  const q = useRivals(serviceId);
  const r = q.data;
  return (
    <section className="card" aria-labelledby="rv-h">
      <div className="mb-2 flex items-center justify-between">
        <h2 id="rv-h" className="text-lg font-semibold">
          Competitors and rating
        </h2>
        <FlagBadges flags={r?.flags} />
      </div>
      <SectionState loading={q.isLoading} error={q.error} rows={3}>
        {r && (
          <div className="space-y-2">
            {r.rivals.length === 0 ? (
              <p className="text-slate-500">
                No rival departures within 30 minutes with a fare captured before the prediction time.
              </p>
            ) : (
              <table className="w-full">
                <thead>
                  <tr>
                    {['Rival', 'Departs', 'Fare', 'Gap to ours'].map((h) => (
                      <th key={h} scope="col" className="py-1 pr-2">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {r.rivals.map((x) => (
                    <tr key={x.label} className="border-t border-slate-100">
                      <td className="py-1 pr-2 font-medium">{x.label}</td>
                      <td className="py-1 pr-2 tabular-nums">{formatTime(x.departure_at)}</td>
                      <td className="py-1 pr-2">
                        <Money value={x.fare} />
                      </td>
                      <td className="py-1 pr-2">
                        <Money value={x.gap_to_ours} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            <p className="text-slate-700">
              Route rating: {r.rating.avg == null ? '—' : r.rating.avg.toFixed(1)}
              {r.rating.count != null ? ` (${r.rating.count.toLocaleString('en-IN')} ratings)` : ''}
            </p>
          </div>
        )}
      </SectionState>
    </section>
  );
}
