import { useRivals } from '../../api/hooks';
import type { NearbyFare, Rival } from '../../api/types';
import { formatDateTime, formatRating } from '../../lib/format';
import FlagBadges from '../FlagBadges';
import Money from '../Money';
import SectionState from '../SectionState';

/** Competitor departures with their fares and the gap to ours (our fare minus theirs). */
function FareTable({ rows }: { rows: (Rival | NearbyFare)[] }) {
  return (
    <table className="w-full">
      <thead>
        <tr>
          {['Operator', 'Departs', 'Fare', 'Gap to ours', 'Fare captured'].map((h) => (
            <th key={h} scope="col" className="py-1 pr-2">
              {h}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((x) => (
          <tr key={`${x.operator}-${x.departure_at}`} className="border-t border-slate-100">
            <td className="py-1 pr-2 font-medium">{x.operator}</td>
            <td className="py-1 pr-2 tabular-nums">{formatDateTime(x.departure_at)}</td>
            <td className="py-1 pr-2">
              <Money value={x.fare} />
            </td>
            <td className="py-1 pr-2">
              <Money value={x.gap_to_ours} />
            </td>
            <td className="py-1 pr-2 text-slate-500">
              {formatDateTime(x.captured_at)}
              {'captured_after_prediction_time' in x &&
                x.captured_after_prediction_time &&
                ', after our seats were counted'}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

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
          <div className="space-y-4">
            <p className="text-slate-700">
              Our fare: <Money value={r.our_fare} /> · Route rating: {formatRating(r.rating)}
            </p>
            <div className="space-y-2">
              <h3 className="font-semibold">Within 30 minutes of ours</h3>
              {r.rivals.length === 0 ? (
                <p className="text-slate-500">{r.note}</p>
              ) : (
                <FareTable rows={r.rivals} />
              )}
            </div>
            <div className="space-y-2">
              <h3 className="font-semibold">Same route, {r.nearby_days} days either side</h3>
              {r.nearby_fares.length === 0 ? (
                <p className="text-slate-500">
                  No competitor departs on this route within {r.nearby_days} days of ours.
                </p>
              ) : (
                <FareTable rows={r.nearby_fares} />
              )}
            </div>
          </div>
        )}
      </SectionState>
    </section>
  );
}
