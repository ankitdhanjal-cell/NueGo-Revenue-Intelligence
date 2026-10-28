import { lazy, Suspense } from 'react';
import { useCurve } from '../../api/hooks';
import FlagBadges from '../FlagBadges';
import SectionState from '../SectionState';

const BookingCurveChart = lazy(() => import('../charts/BookingCurveChart'));

export default function CurveSection({ serviceId }: { serviceId: string }) {
  const q = useCurve(serviceId);
  const c = q.data;
  return (
    <section className="card" aria-labelledby="curve-h">
      <div className="mb-2 flex items-center justify-between">
        <h2 id="curve-h" className="text-lg font-semibold">
          Seats sold so far, against what is normal
        </h2>
        <FlagBadges flags={c?.flags} />
      </div>
      <SectionState loading={q.isLoading} error={q.error} rows={5}>
        {c && (
          <>
            {c.flags.no_history && (
              <p className="mb-2 rounded bg-amber-50 p-2 text-amber-900">
                No history: not enough similar past services for a normal band.
              </p>
            )}
            <Suspense fallback={<div className="h-80 animate-pulse rounded bg-slate-100" />}>
              <BookingCurveChart curve={c} />
            </Suspense>
            {c.curve_note && <p className="mt-2 text-xs text-slate-500">{c.curve_note}</p>}
          </>
        )}
      </SectionState>
    </section>
  );
}
