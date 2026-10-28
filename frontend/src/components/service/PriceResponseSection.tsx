import { lazy, Suspense } from 'react';
import { useElasticity, useSuggestion, useWhatIf } from '../../api/hooks';
import RangeValue from '../RangeValue';
import SectionState from '../SectionState';

const PriceResponseChart = lazy(() => import('../charts/PriceResponseChart'));

interface Props {
  serviceId: string;
  segment: { route_id: string; slot: string; dtg_band: string } | null;
}

export default function PriceResponseSection({ serviceId, segment }: Props) {
  const whatIf = useWhatIf(serviceId);
  const suggestion = useSuggestion(serviceId);
  const el = useElasticity(segment);
  const rows = whatIf.data?.rows ?? [];
  const current =
    rows.length && suggestion.data?.engine_fare != null
      ? rows.reduce((a, b) =>
          Math.abs(b.fare - (suggestion.data?.engine_fare ?? 0)) <
          Math.abs(a.fare - (suggestion.data?.engine_fare ?? 0))
            ? b
            : a,
        ).fare
      : null;
  const e = el.data;
  return (
    <section className="card" aria-labelledby="pr-h">
      <h2 id="pr-h" className="mb-2 text-lg font-semibold">
        How seats change with the fare
      </h2>
      <SectionState
        loading={whatIf.isLoading}
        error={whatIf.error}
        empty={rows.length === 0}
        emptyText="No what-if data for this service."
        rows={4}
      >
        <Suspense fallback={<div className="h-64 animate-pulse rounded bg-slate-100" />}>
          <PriceResponseChart
            rows={rows}
            currentFare={current}
            suggestedFare={suggestion.data?.suggested_fare ?? null}
          />
        </Suspense>
      </SectionState>
      <p className="mt-2 text-sm text-slate-700" aria-live="polite">
        {el.isLoading ? (
          'Loading elasticity…'
        ) : el.error ? (
          'Elasticity unavailable.'
        ) : e?.enough_data ? (
          <>
            Elasticity: <RangeValue range={e.elasticity} format="ratio" /> from {e.n_services} services.
          </>
        ) : (
          <>Not enough data to estimate price response for this segment{e?.reason ? ` (${e.reason})` : ''}.</>
        )}
      </p>
    </section>
  );
}
