import { Link, useLocation, useParams, useSearchParams } from 'react-router-dom';
import { usePnl, useRoutes, useSuggestion } from '../api/hooks';
import type { DeskService } from '../api/types';
import FlagBadges from '../components/FlagBadges';
import SuggestionCard from '../components/SuggestionCard';
import TimeToGo from '../components/TimeToGo';
import CurveSection from '../components/service/CurveSection';
import HistorySection from '../components/service/HistorySection';
import PnlSection from '../components/service/PnlSection';
import PriceResponseSection from '../components/service/PriceResponseSection';
import RivalsSection from '../components/service/RivalsSection';
import StatStrip from '../components/service/StatStrip';
import TrendSection from '../components/service/TrendSection';
import WhatIfSection from '../components/service/WhatIfSection';
import { formatDateTime } from '../lib/format';
import { dtgBandOf, slotOf } from '../lib/segment';

const TABS = [
  { id: 'pace', label: 'Seat pace' },
  { id: 'fares', label: 'Fare options' },
  { id: 'rivals', label: 'Competitors' },
  { id: 'money', label: 'Money' },
  { id: 'history', label: 'Past decisions' },
] as const;
type TabId = (typeof TABS)[number]['id'];

export default function ServicePage() {
  const { id = '' } = useParams();
  const [params, setParams] = useSearchParams();
  const fromDesk = (useLocation().state as { service?: DeskService } | null)?.service;
  const p = usePnl(id).data;
  const suggestion = useSuggestion(id);
  const routes = useRoutes().data?.items ?? [];
  const tab: TabId = TABS.find((t) => t.id === params.get('tab'))?.id ?? 'pace';
  const route = routes.find((r) => r.id === p?.route_id);
  const segment = p
    ? {
        route_id: p.route_id,
        slot: slotOf(new Date(p.departure_at).getHours()),
        dtg_band: dtgBandOf(p.hours_to_departure / 24),
      }
    : null;
  const asOf = p
    ? new Date(new Date(p.departure_at).getTime() - p.hours_to_departure * 3_600_000)
    : undefined;

  return (
    <div className="space-y-6">
      <Link to="/" className="link">
        ← All services
      </Link>
      <header>
        <h1 className="text-3xl font-semibold">{route?.label ?? fromDesk?.route_label ?? id}</h1>
        <p className="mt-1 text-slate-600">
          Departs {p ? formatDateTime(p.departure_at) : '…'} ·{' '}
          {suggestion.data?.coach_type ?? fromDesk?.coach_type ?? 'Coach type unknown'}
        </p>
        {p && asOf && (
          <p className="text-sm text-slate-500">
            The seat count was taken <TimeToGo departure={p.departure_at} now={asOf} /> before departure (
            {formatDateTime(asOf.toISOString())}).
          </p>
        )}
        <div className="mt-1">
          <FlagBadges flags={{ ...p?.flags, ...fromDesk?.flags }} />
        </div>
      </header>

      <StatStrip serviceId={id} pnl={p} />
      <SuggestionCard serviceId={id} />

      <div>
        <h2 className="mb-3 text-xl font-semibold">More detail</h2>
        <div role="tablist" aria-label="Detail" className="mb-4 flex gap-6 border-b border-slate-300">
          {TABS.map((t) => (
            <button
              key={t.id}
              role="tab"
              aria-selected={tab === t.id}
              onClick={() => setParams({ tab: t.id }, { replace: true, state: { service: fromDesk } })}
              className={`-mb-px border-b-2 pb-2 font-medium ${tab === t.id ? 'border-brand-700 text-brand-700' : 'border-transparent text-slate-600 hover:text-slate-900'}`}
            >
              {t.label}
            </button>
          ))}
        </div>
        <div role="tabpanel" className="space-y-4">
          {tab === 'pace' && <CurveSection serviceId={id} />}
          {tab === 'fares' && (
            <>
              <PriceResponseSection serviceId={id} segment={segment} />
              <WhatIfSection serviceId={id} />
            </>
          )}
          {tab === 'rivals' && <RivalsSection serviceId={id} />}
          {tab === 'money' && (
            <>
              <PnlSection serviceId={id} />
              <TrendSection serviceId={id} />
            </>
          )}
          {tab === 'history' && <HistorySection serviceId={id} />}
        </div>
      </div>
    </div>
  );
}
