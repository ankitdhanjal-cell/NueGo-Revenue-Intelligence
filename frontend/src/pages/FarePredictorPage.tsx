import { useState, type FormEvent } from 'react';
import { ApiError } from '../api/client';
import { useFarePredict, useRoutes } from '../api/hooks';
import type { FarePredictInput } from '../api/types';
import RangeValue from '../components/RangeValue';

const iso = (d: Date) => d.toISOString().slice(0, 10);

export default function FarePredictorPage() {
  const today = new Date();
  const max = new Date(today.getTime() + 30 * 86_400_000);
  const routes = useRoutes().data?.items ?? [];
  const [chosenRoute, setRouteId] = useState('');
  const routeId = chosenRoute || routes[0]?.id || '';
  const [date, setDate] = useState(iso(today));
  const [time, setTime] = useState('08:00');
  const [seats, setSeats] = useState('20');
  const [ac, setAc] = useState<'1' | '0'>('1');
  const [sleeper, setSleeper] = useState<'1' | '0'>('0');
  const [error, setError] = useState<string | null>(null);
  const predict = useFarePredict();
  const route = routes.find((r) => r.id === routeId);
  const [used, setUsed] = useState<FarePredictInput | null>(null);

  function submit(e: FormEvent) {
    e.preventDefault();
    const n = Number(seats);
    if (!route || !Number.isInteger(n) || n < 0 || n > route.capacity)
      return setError(`Seats left must be a whole number from 0 to ${route?.capacity ?? 0}.`);
    if (date < iso(today) || date > iso(max))
      return setError('Travel date must be between today and 30 days ahead.');
    setError(null);
    const input: FarePredictInput = {
      route_id: routeId,
      departure_at: `${date}T${time}`,
      available_seats: n,
      ac: ac === '1' ? 1 : 0,
      sleeper: sleeper === '1' ? 1 : 0,
    };
    setUsed(input);
    predict.mutate(input, {
      onError: (err) => setError(err instanceof ApiError ? err.message : 'Prediction failed. Try again.'),
    });
  }

  return (
    <div className="grid max-w-5xl grid-cols-2 gap-6">
      <form onSubmit={submit} className="card space-y-3" noValidate>
        <h1 className="text-3xl font-semibold">Fare checker</h1>
        <p className="-mt-2 text-slate-600">See what the model expects a fare to be. It is only a guide.</p>
        <div>
          <label htmlFor="route" className="label">
            Route
          </label>
          <select id="route" className="input" value={routeId} onChange={(e) => setRouteId(e.target.value)}>
            {routes.map((r) => (
              <option key={r.id} value={r.id}>
                {r.label}
              </option>
            ))}
          </select>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label htmlFor="date" className="label">
              Travel date
            </label>
            <input
              id="date"
              type="date"
              className="input"
              min={iso(today)}
              max={iso(max)}
              value={date}
              onChange={(e) => setDate(e.target.value)}
            />
          </div>
          <div>
            <label htmlFor="time" className="label">
              Departure time
            </label>
            <input
              id="time"
              type="time"
              className="input"
              value={time}
              onChange={(e) => setTime(e.target.value)}
            />
          </div>
        </div>
        <div>
          <label htmlFor="seats" className="label">
            Seats left (0 to {route?.capacity ?? 0})
          </label>
          <input
            id="seats"
            type="number"
            className="input"
            min={0}
            max={route?.capacity}
            value={seats}
            onChange={(e) => setSeats(e.target.value)}
          />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label htmlFor="ac" className="label">
              Air conditioning
            </label>
            <select
              id="ac"
              className="input"
              value={ac}
              onChange={(e) => setAc(e.target.value === '1' ? '1' : '0')}
            >
              <option value="1">AC</option>
              <option value="0">Non-AC</option>
            </select>
          </div>
          <div>
            <label htmlFor="sleeper" className="label">
              Seating
            </label>
            <select
              id="sleeper"
              className="input"
              value={sleeper}
              onChange={(e) => setSleeper(e.target.value === '1' ? '1' : '0')}
            >
              <option value="0">Seater</option>
              <option value="1">Sleeper</option>
            </select>
          </div>
        </div>
        {error && (
          <p role="alert" className="text-sm text-red-700">
            {error}
          </p>
        )}
        <button type="submit" className="btn btn-primary" disabled={predict.isPending}>
          {predict.isPending ? 'Checking…' : 'Check fare'}
        </button>
      </form>

      <div className="card">
        <h2 className="mb-2 font-semibold">Result</h2>
        {!predict.data && !predict.isPending && (
          <p className="text-slate-500">Fill in the form to see a reference fare.</p>
        )}
        {predict.data && used && (
          <div className="space-y-2">
            <div className="text-2xl font-semibold">
              <RangeValue range={predict.data.fare} format="inr" />
            </div>
            <p className="text-slate-600">Reference fare learned from past pricing. Not a suggestion.</p>
            <dl className="space-y-1 text-xs text-slate-600">
              <div>
                <dt className="inline font-medium">Model: </dt>
                <dd className="inline">{predict.data.model_version}</dd>
              </div>
              <div>
                <dt className="inline font-medium">Inputs used: </dt>
                <dd className="inline">
                  {route?.label}, {used.departure_at.replace('T', ' ')}, {used.available_seats} seats left,{' '}
                  {used.ac ? 'AC' : 'Non-AC'} {used.sleeper ? 'Sleeper' : 'Seater'}
                </dd>
              </div>
              <div>
                <dt className="inline font-medium">Competitor rows used: </dt>
                <dd className="inline">{predict.data.competitor_rows_used}</dd>
              </div>
              {predict.data.assumptions && (
                <div>
                  <dt className="inline font-medium">Assumption: </dt>
                  <dd className="inline">{predict.data.assumptions}</dd>
                </div>
              )}
            </dl>
            {predict.data.insufficient_data && (
              <p className="rounded bg-amber-50 p-2 text-amber-900">
                Low confidence: little competitor data behind this prediction.
              </p>
            )}
          </div>
        )}
        {predict.isSuccess && !predict.data && (
          <p className="rounded bg-amber-50 p-2 text-amber-900">
            Not enough data to predict a fare for these inputs.
          </p>
        )}
      </div>
    </div>
  );
}
