import { Link } from 'react-router-dom';
import { useSuggestion } from '../../api/hooks';
import type { DeskService } from '../../api/types';
import { formatSeats } from '../../lib/format';
import BlockedNotice from '../BlockedNotice';
import Modal from '../Modal';
import Money from '../Money';
import RangeValue from '../RangeValue';
import ReasonList from '../ReasonList';
import SectionState from '../SectionState';

/** Quick look from the desk: the gap, the fares, the expected change, the floor and why. */
export default function ServicePanel({ service, onClose }: { service: DeskService; onClose: () => void }) {
  const q = useSuggestion(service.service_id);
  const s = q.data;
  const gap = service.gap_to_checkpoint;
  return (
    <Modal title={service.route_label} onClose={onClose} side>
      <dl className="space-y-2 text-sm">
        <Row label="Gap to checkpoint">
          {gap == null ? 'No history' : `${formatSeats(Math.abs(gap))} seats ${gap < 0 ? 'behind' : 'ahead'}`}
        </Row>
        <Row label="Fare on sale">
          <Money value={service.fare_on_sale} />
        </Row>
      </dl>
      <SectionState loading={q.isLoading} error={q.error} rows={3}>
        {s && (
          <div className="mt-4 space-y-4">
            {s.suggested_fare == null ? (
              <BlockedNotice suggestion={s} />
            ) : (
              <dl className="space-y-2 text-sm">
                <Row label="Suggested fare">
                  <Money value={s.suggested_fare} />
                </Row>
                <Row label="Extra seats">
                  <RangeValue range={s.extra_seats} format="seats" missing="Not claimed" />
                </Row>
                <Row label="Margin change">
                  <RangeValue range={s.margin_change} format="inr" missing="Not claimed" />
                </Row>
              </dl>
            )}
            <dl className="text-sm">
              <Row label="Cost floor">
                <Money value={s.floor?.value} missing="Floor missing" />
              </Row>
            </dl>
            {s.reasons.length > 0 && <ReasonList reasons={s.reasons} />}
          </div>
        )}
      </SectionState>
      <Link
        to={`/services/${service.service_id}`}
        state={{ service }}
        className="btn btn-primary mt-6 inline-block"
      >
        Open full review
      </Link>
    </Modal>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-2">
      <dt className="w-36 text-slate-600">{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}
