import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useDeskServices, useRoutes } from '../api/hooks';
import type { DeskFilters, DeskService } from '../api/types';
import SectionState from '../components/SectionState';
import DeskTable from '../components/desk/DeskTable';
import ServicePanel from '../components/desk/ServicePanel';
import SummaryLine from '../components/desk/SummaryLine';

const TABS: { id: DeskFilters['window']; label: string }[] = [
  { id: 'today', label: 'Today' },
  { id: 'tomorrow', label: 'Tomorrow' },
  { id: 'next30', label: 'Next 30 days' },
  { id: 'earlier', label: 'Already departed' },
];

const STEPS = [
  'Pick a service from the list',
  'Read our suggested fare and why',
  'Approve it, change it or reject it',
];

function isWindow(v: string | null): v is DeskFilters['window'] {
  return v === 'today' || v === 'tomorrow' || v === 'next30' || v === 'earlier';
}

export default function DeskPage() {
  const [params, setParams] = useSearchParams();
  const windowParam = params.get('window');
  const filters: DeskFilters = {
    window: isWindow(windowParam) ? windowParam : 'next30',
    corridor_id: params.get('corridor') ?? '',
    page: Number(params.get('page') ?? 1),
  };
  const q = useDeskServices(filters);
  const routes = useRoutes().data?.items ?? [];
  const [showMoney, setShowMoney] = useState(false);
  const [showCancelled, setShowCancelled] = useState(false);
  const [selected, setSelected] = useState<DeskService | null>(null);

  function update(next: Partial<Record<'window' | 'corridor' | 'page', string>>) {
    const p = new URLSearchParams(params);
    Object.entries(next).forEach(([k, v]) => (v ? p.set(k, v) : p.delete(k)));
    if (!('page' in next)) p.delete('page');
    setParams(p);
  }

  const data = q.data;
  const ranked = data?.items.filter((s) => s.rank != null) ?? [];
  const unranked = data?.items.filter((s) => s.rank == null) ?? [];
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;
  const empty = data?.items.length === 0 && data.cancelled.length === 0;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold">Services to review</h1>
        <p className="mt-1 text-slate-600">The services that need you most are at the top.</p>
        <ol className="mt-3 flex gap-6 text-sm text-slate-700">
          {STEPS.map((s, i) => (
            <li key={s} className="flex items-center gap-2">
              <span className="flex h-5 w-5 items-center justify-center rounded-full border border-slate-400 text-xs font-semibold">
                {i + 1}
              </span>
              {s}
            </li>
          ))}
        </ol>
      </div>

      <SummaryLine filters={filters} />

      <div className="flex items-end justify-between">
        <div role="tablist" aria-label="Departure window" className="flex gap-6 border-b border-slate-300">
          {TABS.map((t) => (
            <button
              key={t.id}
              role="tab"
              aria-selected={filters.window === t.id}
              onClick={() => update({ window: t.id })}
              className={`-mb-px border-b-2 pb-2 font-medium ${filters.window === t.id ? 'border-brand-700 text-brand-700' : 'border-transparent text-slate-600 hover:text-slate-900'}`}
            >
              {t.label}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-4">
          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input type="checkbox" checked={showMoney} onChange={(e) => setShowMoney(e.target.checked)} />
            Show money columns
          </label>
          <div className="flex items-center gap-2">
            <label htmlFor="corridor" className="text-sm text-slate-700">
              Route
            </label>
            <select
              id="corridor"
              className="input w-48"
              value={filters.corridor_id}
              onChange={(e) => update({ corridor: e.target.value })}
            >
              <option value="">All routes</option>
              {routes.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.label}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      <SectionState loading={q.isLoading} error={q.error} rows={6}>
        {empty && (
          <div className="border-y border-slate-300 py-10 text-center text-slate-600">
            <p className="font-medium text-slate-800">No services in this window.</p>
            <p className="mt-1">
              The data is a sample of past and upcoming departures, so some days have none.
            </p>
            {filters.window !== 'earlier' && (
              <button className="btn mt-4" onClick={() => update({ window: 'earlier' })}>
                See services that already departed
              </button>
            )}
          </div>
        )}
        {data && !empty && (
          <div className="space-y-6">
            <DeskTable onSelect={setSelected} rows={ranked} showMoney={showMoney} />
            <div className="flex items-center justify-between text-sm text-slate-600">
              <span>
                {data.total} services · page {data.page} of {pages}
              </span>
              <span className="flex gap-2">
                <button
                  className="btn"
                  disabled={filters.page <= 1}
                  onClick={() => update({ page: String(filters.page - 1) })}
                >
                  Previous
                </button>
                <button
                  className="btn"
                  disabled={filters.page >= pages}
                  onClick={() => update({ page: String(filters.page + 1) })}
                >
                  Next
                </button>
              </span>
            </div>
            {unranked.length > 0 && (
              <section aria-labelledby="unranked-h">
                <h2 id="unranked-h" className="text-lg font-semibold">
                  Cannot be ranked yet
                </h2>
                <p className="mb-2 text-sm text-slate-600">
                  We do not know what these services cost to run, so we cannot say how much they matter.
                </p>
                <DeskTable onSelect={setSelected} rows={unranked} showMoney={showMoney} showRank={false} />
              </section>
            )}
            {data.cancelled.length > 0 && (
              <section>
                <button
                  className="btn-quiet btn px-0"
                  aria-expanded={showCancelled}
                  onClick={() => setShowCancelled((v) => !v)}
                >
                  {showCancelled ? 'Hide' : 'Show'} cancelled services ({data.cancelled.length})
                </button>
                {showCancelled && (
                  <div className="mt-2">
                    <p className="mb-2 text-sm text-slate-600">
                      Cancelled services are not ranked and are left out of the totals.
                    </p>
                    <DeskTable
                      onSelect={setSelected}
                      rows={data.cancelled}
                      showMoney={showMoney}
                      showRank={false}
                    />
                  </div>
                )}
              </section>
            )}
          </div>
        )}
      </SectionState>
      {selected && <ServicePanel service={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}
