import { useState } from 'react';
import { useTotals } from '../api/hooks';
import Money from '../components/Money';
import SectionState from '../components/SectionState';
import { formatPct } from '../lib/format';

const GROUPS = [
  { id: 'corridor', label: 'Corridor' },
  { id: 'date', label: 'Date' },
  { id: 'coach_type', label: 'Coach type' },
  { id: 'channel', label: 'Channel' },
];

export default function TotalsPage() {
  const [group, setGroup] = useState('corridor');
  const q = useTotals(group);
  const rows = q.data?.rows ?? [];
  const sum = (k: 'services' | 'revenue' | 'cost_to_run' | 'profit') => rows.reduce((s, r) => s + r[k], 0);
  const revenue = sum('revenue');
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-semibold">Money summary</h1>
          <p className="mt-1 text-slate-600">What the services earned and cost to run, added up.</p>
        </div>
        <div role="tablist" aria-label="Group by" className="flex gap-1 rounded-lg bg-slate-200 p-1">
          {GROUPS.map((g) => (
            <button
              key={g.id}
              role="tab"
              aria-selected={group === g.id}
              onClick={() => setGroup(g.id)}
              className={`rounded-md px-3 py-1 text-sm font-medium ${group === g.id ? 'bg-white shadow-sm' : 'text-slate-600'}`}
            >
              {g.label}
            </button>
          ))}
        </div>
      </div>
      <p className="text-xs text-slate-500">Cancelled services are left out.</p>
      <SectionState
        loading={q.isLoading}
        error={q.error}
        empty={rows.length === 0}
        emptyText="No data for this grouping."
      >
        <table className="w-full rounded-lg border border-slate-200 bg-white">
          <thead className="bg-slate-50">
            <tr>
              {[
                GROUPS.find((g) => g.id === group)?.label ?? 'Group',
                'Services',
                'Revenue',
                'Cost to run',
                'Margin',
                'Margin %',
              ].map((h) => (
                <th key={h} scope="col" className="px-3 py-2">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.group} className="border-t border-slate-100">
                <td className="px-3 py-2 font-medium">{r.group}</td>
                <td className="px-3 py-2 tabular-nums">{r.services}</td>
                <td className="px-3 py-2">
                  <Money value={r.revenue} />
                </td>
                <td className="px-3 py-2">
                  <Money value={r.cost_to_run} />
                </td>
                <td className="px-3 py-2">
                  <Money value={r.profit} colorNegative />
                </td>
                <td className="px-3 py-2 tabular-nums">{formatPct(r.margin_pct)}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="border-t-2 border-slate-300 bg-slate-50 font-semibold">
              <td className="px-3 py-2">Total</td>
              <td className="px-3 py-2 tabular-nums">{sum('services')}</td>
              <td className="px-3 py-2">
                <Money value={revenue} />
              </td>
              <td className="px-3 py-2">
                <Money value={sum('cost_to_run')} />
              </td>
              <td className="px-3 py-2">
                <Money value={sum('profit')} colorNegative />
              </td>
              <td className="px-3 py-2 tabular-nums">
                {formatPct(revenue > 0 ? (sum('profit') / revenue) * 100 : null)}
              </td>
            </tr>
          </tfoot>
        </table>
      </SectionState>
    </div>
  );
}
