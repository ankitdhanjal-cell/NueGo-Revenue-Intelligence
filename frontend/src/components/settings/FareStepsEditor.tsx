import { useState } from 'react';
import { generateFareSteps, parseFareSteps } from '../../lib/fareSteps';
import { formatINR } from '../../lib/format';

interface Props {
  text: string;
  onChange: (text: string) => void;
  disabled: boolean;
  error?: string;
}

export default function FareStepsEditor({ text, onChange, disabled, error }: Props) {
  const [from, setFrom] = useState('200');
  const [to, setTo] = useState('1500');
  const [every, setEvery] = useState('10');
  const steps = parseFareSteps(text);
  const valid = steps.length > 0 && steps.every(Number.isFinite);
  const generated = generateFareSteps(Number(from), Number(to), Number(every));

  return (
    <fieldset className="space-y-2">
      <legend className="label">Allowed fare steps (comma or space separated, ascending)</legend>
      <div className="flex flex-wrap items-end gap-2 rounded bg-slate-50 p-2">
        {[
          ['From ₹', from, setFrom],
          ['To ₹', to, setTo],
          ['Every ₹', every, setEvery],
        ].map(([label, value, set]) => (
          <div key={String(label)}>
            <label className="label" htmlFor={`gen-${String(label)}`}>
              {String(label)}
            </label>
            <input
              id={`gen-${String(label)}`}
              type="number"
              className="input w-24"
              value={String(value)}
              disabled={disabled}
              onChange={(e) => (set as (v: string) => void)(e.target.value)}
            />
          </div>
        ))}
        <button
          type="button"
          className="btn"
          disabled={disabled || generated.length === 0}
          onClick={() => onChange(generated.join(', '))}
        >
          Generate {generated.length > 0 ? `(${generated.length} steps)` : ''}
        </button>
      </div>
      <label htmlFor="steps" className="sr-only">
        Fare steps
      </label>
      <textarea
        id="steps"
        rows={5}
        className="input font-mono"
        value={text}
        disabled={disabled}
        aria-invalid={!!error}
        onChange={(e) => onChange(e.target.value)}
      />
      <p className="text-xs text-slate-500">
        {valid
          ? `${steps.length} steps, ${formatINR(steps[0])} to ${formatINR(steps[steps.length - 1])}`
          : 'No valid steps yet.'}
      </p>
      {error && (
        <p role="alert" className="text-sm text-red-700">
          {error}
        </p>
      )}
    </fieldset>
  );
}
