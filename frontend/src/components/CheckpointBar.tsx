import type { Range } from '../api/types';
import { formatSeats } from '../lib/format';

interface Props {
  sold: number;
  capacity: number;
  checkpoint: Range | null;
}

/** Seats sold out of capacity. The pale band is the normal range for now and the tick is the expected number. */
export default function CheckpointBar({ sold, capacity, checkpoint }: Props) {
  const pct = (v: number) => `${Math.min(100, Math.max(0, (v / capacity) * 100))}%`;
  const label = checkpoint
    ? `${formatSeats(sold)} of ${formatSeats(capacity)} seats sold, checkpoint ${formatSeats(checkpoint.mid)} (${formatSeats(checkpoint.low)}–${formatSeats(checkpoint.high)})`
    : `${formatSeats(sold)} of ${formatSeats(capacity)} seats sold, no checkpoint`;
  return (
    <div className="flex items-center gap-3">
      <div role="img" aria-label={label} className="relative h-2.5 w-40 rounded-sm bg-slate-200">
        {checkpoint && (
          <div
            className="absolute inset-y-0 bg-brand-100"
            style={{
              left: pct(checkpoint.low),
              width: `${((checkpoint.high - checkpoint.low) / capacity) * 100}%`,
            }}
          />
        )}
        <div className="absolute inset-y-0 left-0 rounded-sm bg-brand-700" style={{ width: pct(sold) }} />
        {checkpoint && (
          <div className="absolute -inset-y-1 w-0.5 bg-ochre-700" style={{ left: pct(checkpoint.mid) }} />
        )}
      </div>
      <span className="text-sm tabular-nums text-slate-700">
        {formatSeats(sold)} of {formatSeats(capacity)}
      </span>
    </div>
  );
}
