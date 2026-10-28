import { useMemo } from 'react';
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { WhatIfRow } from '../../api/types';
import { formatINR } from '../../lib/format';

interface Props {
  rows: WhatIfRow[];
  currentFare: number | null;
  suggestedFare: number | null;
}

export default function PriceResponseChart({ rows, currentFare, suggestedFare }: Props) {
  const data = useMemo(
    () =>
      rows.map((r) => ({
        fare: r.fare,
        mid: r.seats.mid,
        range: [r.seats.low, r.seats.high] as [number, number],
      })),
    [rows],
  );
  return (
    <div role="img" aria-label="Price response: expected final seats at each allowed fare" className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 16, right: 16, bottom: 16, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e7e0d2" />
          <XAxis
            type="number"
            dataKey="fare"
            domain={['dataMin', 'dataMax']}
            tickFormatter={(v: number) => formatINR(v)}
            label={{ value: 'Fare', position: 'insideBottom', offset: -8 }}
          />
          <YAxis width={48} label={{ value: 'Seats', angle: -90, position: 'insideLeft' }} />
          <Tooltip
            labelFormatter={(l) => formatINR(Number(l))}
            formatter={(v: number | number[]) => (Array.isArray(v) ? `${v[0]}–${v[1]}` : v)}
          />
          <Area
            dataKey="range"
            name="Range (low–high)"
            stroke="none"
            fill="#2c3e5c"
            fillOpacity={0.2}
            isAnimationActive={false}
          />
          <Line
            dataKey="mid"
            name="Expected (mid)"
            stroke="#2c3e5c"
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
          {currentFare != null && (
            <ReferenceLine
              x={currentFare}
              stroke="#57534e"
              strokeDasharray="4 3"
              label={{ value: 'Current', position: 'top' }}
            />
          )}
          {suggestedFare != null && (
            <ReferenceLine
              x={suggestedFare}
              stroke="#a3302b"
              label={{ value: 'Suggested', position: 'insideTopRight', fill: '#a3302b' }}
            />
          )}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
