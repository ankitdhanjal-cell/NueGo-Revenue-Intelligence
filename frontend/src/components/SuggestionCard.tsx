import { useSuggestion } from '../api/hooks';
import BlockedNotice from './BlockedNotice';
import DecisionButtons from './DecisionButtons';
import FlagBadges from './FlagBadges';
import Money from './Money';
import RangeValue from './RangeValue';
import ReasonList from './ReasonList';
import SectionState from './SectionState';

/** The main thing on the review page: the model's fare, the suggested fare inside the rules, why, and the buttons. */
export default function SuggestionCard({ serviceId }: { serviceId: string }) {
  const q = useSuggestion(serviceId);
  const s = q.data;
  const p = s?.predicted_fare;
  return (
    <section className="card" aria-labelledby="suggestion-h">
      <h2 id="suggestion-h" className="mb-4 text-xl font-semibold">
        Our suggestion
      </h2>
      <SectionState loading={q.isLoading} error={q.error} rows={4}>
        {s && (
          <div className="space-y-5">
            <div className="grid grid-cols-2 gap-x-10">
              <div>
                <div className="text-sm text-slate-600">Predicted fare</div>
                <div className="font-serif text-4xl font-semibold tabular-nums">
                  {p ? (
                    <RangeValue range={p} format="inr" />
                  ) : (
                    <span className="text-slate-400">No prediction</span>
                  )}
                </div>
                <div className="mt-1 text-sm text-slate-600">From the linear regression fare model</div>
              </div>
              <div>
                <div className="text-sm text-slate-600">Suggested fare, inside your pricing rules</div>
                <div className="font-serif text-4xl font-semibold tabular-nums">
                  {s.suggested_fare == null ? (
                    <span className="text-slate-400">None</span>
                  ) : (
                    <Money value={s.suggested_fare} />
                  )}
                </div>
                <div className="mt-1 text-sm text-slate-600">
                  Fare now <Money value={s.engine_fare} />
                </div>
              </div>
            </div>

            {s.suggested_fare == null ? (
              <BlockedNotice suggestion={s} />
            ) : (
              <dl className="space-y-1 border-t border-slate-200 pt-4 text-sm">
                <div className="flex gap-2">
                  <dt className="w-44 text-slate-600">Seats at the end</dt>
                  <dd>
                    <RangeValue range={s.expected_seats} format="seats" />
                  </dd>
                </div>
                <div className="flex gap-2">
                  <dt className="w-44 text-slate-600">Margin at this fare</dt>
                  <dd>
                    <RangeValue range={s.expected_margin} format="inr" missing="Cost missing" />
                  </dd>
                </div>
                <div className="flex gap-2">
                  <dt className="w-44 text-slate-600">Change against now</dt>
                  <dd>
                    {s.extra_seats && s.margin_change ? (
                      <>
                        <RangeValue range={s.extra_seats} format="seats" /> seats,{' '}
                        <RangeValue range={s.margin_change} format="inr" />
                      </>
                    ) : (
                      <span className="text-slate-500">
                        Not claimed: the seat model does not show a reliable price response
                      </span>
                    )}
                  </dd>
                </div>
              </dl>
            )}

            {s.reasons.length > 0 && (
              <div>
                <h3 className="mb-1 font-semibold">Why this fare</h3>
                <ReasonList reasons={s.reasons} />
              </div>
            )}
            <FlagBadges flags={s.flags} />

            {s.suggested_fare != null && (
              <div className="border-t border-slate-200 pt-4">
                <p className="mb-2 text-sm text-slate-600">
                  What would you like to do? Nothing is changed in the pricing engine; your choice is only
                  recorded.
                </p>
                <DecisionButtons suggestion={s} />
              </div>
            )}

            <details className="text-sm">
              <summary className="cursor-pointer font-medium text-brand-700">Other numbers</summary>
              <dl className="mt-2 space-y-1">
                <div className="flex gap-2">
                  <dt className="w-44 text-slate-600">Cost floor</dt>
                  <dd>
                    <Money value={s.floor?.value} missing="Floor missing" />{' '}
                    <span className="text-slate-500">({s.floor?.type})</span>
                  </dd>
                </div>
                {p?.competitor_rows_used != null && (
                  <div className="flex gap-2">
                    <dt className="w-44 text-slate-600">Competitor rows used</dt>
                    <dd>{p.competitor_rows_used} (route-level summary)</dd>
                  </div>
                )}
              </dl>
            </details>
          </div>
        )}
      </SectionState>
    </section>
  );
}
