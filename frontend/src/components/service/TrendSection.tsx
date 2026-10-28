import { useTrend } from '../../api/hooks';
import { formatDate, formatPct } from '../../lib/format';
import Money from '../Money';
import SectionState from '../SectionState';

/** Same route, same weekday, previous 8 weeks (FR-PNL-006). */
export default function TrendSection({ serviceId }: { serviceId: string }) {
  const q = useTrend(serviceId);
  const points = q.data?.points ?? [];
  return (
    <section className="card" aria-labelledby="trend-h">
      <h2 id="trend-h" className="mb-2 text-lg font-semibold">
        Same weekday, last 8 weeks
      </h2>
      <SectionState
        loading={q.isLoading}
        error={q.error}
        empty={points.length === 0}
        emptyText={`No earlier ${q.data?.weekday ?? ''} service on this route in the previous 8 weeks.`}
      >
        <table className="w-full">
          <thead>
            <tr>
              {['Departed', 'Seats filled', 'Revenue', 'Margin'].map((h) => (
                <th key={h} scope="col" className="px-2 py-1">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {points.map((p) => (
              <tr key={p.departure_at} className="border-t border-slate-100">
                <td className="px-2 py-1">{formatDate(p.departure_at)}</td>
                <td className="px-2 py-1">{formatPct(p.load_pct)}</td>
                <td className="px-2 py-1">
                  <Money value={p.revenue} />
                </td>
                <td className="px-2 py-1">
                  <Money value={p.margin} colorNegative missing="Cost missing" />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </SectionState>
    </section>
  );
}
