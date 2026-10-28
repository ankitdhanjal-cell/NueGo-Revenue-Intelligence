import { useCurve, useSuggestion } from '../../api/hooks';
import type { Pnl } from '../../api/types';
import { gapRange } from '../../lib/gap';
import Money from '../Money';
import RangeValue from '../RangeValue';

/** Where the service stands, in four numbers. */
export default function StatStrip({ serviceId, pnl }: { serviceId: string; pnl: Pnl | undefined }) {
  const curve = useCurve(serviceId);
  const sug = useSuggestion(serviceId);
  const expected = curve.data?.forecast.at(-1)?.seats ?? null;
  const gap = pnl ? gapRange(pnl.seats_sold, expected) : null;
  const items: [string, React.ReactNode][] = [
    ['Seats sold', pnl ? `${pnl.seats_sold} of ${pnl.total_seats}` : '—'],
    ['Expected by now', <RangeValue key="e" range={expected} format="seats" missing="No forecast" />],
    ['Compared with plan', <RangeValue key="g" range={gap} format="seats" missing="No forecast" />],
    ['Fare now', <Money key="f" value={sug.data?.engine_fare} />],
  ];
  return (
    <dl className="grid grid-cols-4 divide-x divide-slate-300 border-y border-slate-300 py-4">
      {items.map(([label, value], i) => (
        <div key={label} className={i === 0 ? 'pr-6' : 'px-6'}>
          <dt className="text-sm text-slate-600">{label}</dt>
          <dd className="font-serif text-2xl font-semibold tabular-nums">{value}</dd>
        </div>
      ))}
    </dl>
  );
}
