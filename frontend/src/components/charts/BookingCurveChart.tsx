import { useMemo } from 'react';
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ReferenceDot,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { Curve } from '../../api/types';

interface Row {
  dtg: number;
  band?: [number, number];
  p50?: number;
  actual?: number;
  forecastRange?: [number, number];
  forecast?: number;
}

/** One row per days-to-go value, so every series shares the same x axis (30 on the left, 0 on the right). */
function curveRows(c: Curve): Row[] {
  const rows = new Map<number, Row>();
  const at = (dtg: number) => {
    const key = Math.round(dtg * 100) / 100;
    const row = rows.get(key) ?? { dtg: key };
    rows.set(key, row);
    return row;
  };
  c.band.forEach((b) => Object.assign(at(b.dtg), { band: [b.p10, b.p90], p50: b.p50 }));
  c.actual.forEach((a) => Object.assign(at(a.dtg), { actual: a.seats }));
  c.forecast.forEach((f) =>
    Object.assign(at(f.dtg), { forecastRange: [f.seats.low, f.seats.high], forecast: f.seats.mid }),
  );
  return [...rows.values()].sort((a, b) => b.dtg - a.dtg);
}

export default function BookingCurveChart({ curve }: { curve: Curve }) {
  const data = useMemo(() => curveRows(curve), [curve]);
  const capacity = curve.capacity ?? 40;
  return (
    <div
      role="img"
      aria-label="Booking curve: seats sold by days to departure, with normal band and forecast"
      className="h-80"
    >
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 8, right: 16, bottom: 16, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e7e0d2" />
          <XAxis
            type="number"
            dataKey="dtg"
            reversed
            domain={[30, 0]}
            ticks={[30, 25, 20, 15, 10, 5, 0]}
            label={{ value: 'Days to go', position: 'insideBottom', offset: -8 }}
          />
          <YAxis domain={[0, capacity]} label={{ value: 'Seats', angle: -90, position: 'insideLeft' }} />
          <Tooltip
            formatter={(v: number | number[]) => (Array.isArray(v) ? `${v[0]}–${v[1]}` : v)}
            labelFormatter={(l) => `${l} days to go`}
          />
          <Legend verticalAlign="top" height={28} />
          <Area
            dataKey="band"
            name="Normal range (p10–p90)"
            stroke="none"
            fill="#2c3e5c"
            fillOpacity={0.18}
            connectNulls
            isAnimationActive={false}
          />
          <Line
            dataKey="p50"
            name="Normal (p50)"
            stroke="#2c3e5c"
            strokeDasharray="5 4"
            dot={false}
            connectNulls
            isAnimationActive={false}
          />
          <Area
            dataKey="forecastRange"
            name="Forecast range"
            stroke="none"
            fill="#a8761a"
            fillOpacity={0.15}
            connectNulls
            isAnimationActive={false}
          />
          <Line
            dataKey="forecast"
            name="Forecast"
            stroke="#a8761a"
            strokeOpacity={0.7}
            dot={{ r: 3 }}
            connectNulls
            isAnimationActive={false}
          />
          <Line
            dataKey="actual"
            name="Seats sold"
            stroke="#1c1917"
            strokeWidth={2}
            dot={{ r: 4 }}
            connectNulls
            isAnimationActive={false}
          />
          {curve.band.map((b) => (
            <ReferenceDot
              key={b.dtg}
              x={b.dtg}
              y={b.p50}
              r={4}
              fill="#2c3e5c"
              stroke="white"
              ifOverflow="extendDomain"
            />
          ))}
          {curve.today_dtg != null && (
            <ReferenceLine
              x={curve.today_dtg}
              stroke="#a3302b"
              label={{ value: 'Today', position: 'insideTopLeft', fill: '#a3302b' }}
            />
          )}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
