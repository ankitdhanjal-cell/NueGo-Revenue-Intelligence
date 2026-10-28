import { Link, useNavigate } from 'react-router-dom';
import type { DeskService } from '../../api/types';
import { formatDate, formatTime } from '../../lib/format';
import CheckpointBar from '../CheckpointBar';
import FlagBadges from '../FlagBadges';
import Money from '../Money';
import RangeValue from '../RangeValue';
import StatusChip from '../StatusChip';
import TimeToGo from '../TimeToGo';

function rankTitle(s: DeskService): string {
  const p = s.score_parts;
  return p
    ? `Priority score ${p.score.toFixed(2)}: seats behind ${p.behind_part.toFixed(2)}, money lost ${p.margin_part.toFixed(2)}`
    : 'No rank';
}

interface Props {
  rows: DeskService[];
  showMoney: boolean;
  showRank?: boolean;
}

/** One row per service. A click anywhere on the row opens the review page. */
export default function DeskTable({ rows, showMoney, showRank = true }: Props) {
  const navigate = useNavigate();
  const open = (s: DeskService) => navigate(`/services/${s.service_id}`, { state: { service: s } });
  const heads = [
    '#',
    'Service',
    'Departs',
    'Seats sold',
    'Expected by now',
    'Fare now',
    ...(showMoney ? ['Revenue', 'Cost', 'Margin'] : []),
    'How it is going',
    '',
  ];
  return (
    <div className="overflow-x-auto border-y border-slate-300 bg-white">
      <table className="w-full border-collapse">
        <thead>
          <tr className="border-b border-slate-300">
            {heads.map((h, i) => (
              <th key={h || i} scope="col" className="px-3 py-2.5">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((s) => (
            <tr
              key={s.service_id}
              tabIndex={0}
              onClick={() => open(s)}
              onKeyDown={(e) => e.key === 'Enter' && open(s)}
              className="cursor-pointer border-b border-slate-200 last:border-0 hover:bg-paper focus:bg-paper focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-brand-600"
            >
              <td className="w-10 px-3 py-3.5 text-slate-500">
                {showRank && s.rank != null ? (
                  <span
                    title={rankTitle(s)}
                    aria-label={`Rank ${s.rank}. ${rankTitle(s)}`}
                    className="cursor-help font-semibold tabular-nums text-slate-900"
                  >
                    {s.rank}
                  </span>
                ) : (
                  '—'
                )}
              </td>
              <td className="px-3 py-3.5">
                <div className="whitespace-nowrap font-semibold">{s.route_label}</div>
                <div className="text-sm text-slate-600">
                  {formatTime(s.departure_at)} · {s.coach_type ?? 'Coach type unknown'}
                </div>
              </td>
              <td className="px-3 py-3.5">
                <div className="whitespace-nowrap">{formatDate(s.departure_at)}</div>
                <div className="whitespace-nowrap text-xs text-slate-500">
                  seats counted <TimeToGo departure={s.departure_at} now={s.as_of} /> before
                </div>
              </td>
              <td className="px-3 py-3.5">
                <CheckpointBar sold={s.seats_sold} capacity={s.capacity} checkpoint={s.checkpoint} />
              </td>
              <td className="px-3 py-3.5">
                <RangeValue range={s.checkpoint} format="seats" missing="No history" />
              </td>
              <td className="px-3 py-3.5">
                <Money value={s.fare_on_sale} />
              </td>
              {showMoney && (
                <>
                  <td className="px-3 py-3.5">
                    <Money value={s.revenue} />
                  </td>
                  <td className="px-3 py-3.5">
                    <Money value={s.cost_to_run} missing="Cost missing" />
                  </td>
                  <td className="px-3 py-3.5">
                    <Money value={s.margin_now} colorNegative missing="Cost missing" />
                  </td>
                </>
              )}
              <td className="px-3 py-3.5">
                <div>
                  <StatusChip status={s.status} />
                </div>
                <FlagBadges flags={s.flags} />
              </td>
              <td className="px-3 py-3.5 text-right">
                <Link
                  to={`/services/${s.service_id}`}
                  state={{ service: s }}
                  className="btn"
                  onClick={(e) => e.stopPropagation()}
                >
                  Review
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
