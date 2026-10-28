import { usePnl } from '../../api/hooks';
import FlagBadges from '../FlagBadges';
import Money from '../Money';
import RangeValue from '../RangeValue';
import SectionState from '../SectionState';

export default function PnlSection({ serviceId }: { serviceId: string }) {
  const q = usePnl(serviceId);
  const p = q.data;
  const items: [string, React.ReactNode][] = p
    ? [
        ['Revenue so far', <Money key="r" value={p.revenue} />],
        ['Cost to run', <Money key="c" value={p.cost_to_run} missing="Cost missing" />],
        ['Margin now', <Money key="m" value={p.margin_now} colorNegative missing="Cost missing" />],
        [
          'Expected margin',
          <RangeValue key="e" range={p.expected_margin} format="inr" missing="Not available" />,
        ],
      ]
    : [];
  return (
    <section className="card" aria-labelledby="pnl-h">
      <div className="mb-2 flex items-center justify-between">
        <h2 id="pnl-h" className="text-lg font-semibold">
          Money
        </h2>
        <FlagBadges flags={p?.flags} />
      </div>
      <SectionState loading={q.isLoading} error={q.error} rows={3}>
        <dl className="grid grid-cols-2 gap-x-4 gap-y-2">
          {items.map(([label, value]) => (
            <div key={label}>
              <dt className="text-xs text-slate-500">{label}</dt>
              <dd className="font-medium">{value}</dd>
            </div>
          ))}
        </dl>
      </SectionState>
    </section>
  );
}
