import { useState, type FormEvent } from 'react';
import { ApiError } from '../api/client';
import { useRules, useUpdateRules } from '../api/hooks';
import type { Rules, RulesInput } from '../api/types';
import SectionState from '../components/SectionState';
import { useToast } from '../components/Toast';
import FareStepsEditor from '../components/settings/FareStepsEditor';
import OwnersEditor from '../components/settings/OwnersEditor';
import { parseFareSteps, validateFareSteps } from '../lib/fareSteps';
import { formatDateTime } from '../lib/format';
import { useUser } from '../lib/user';

interface FormState {
  floor_switch_hours: string;
  ceiling: string;
  state_cap: string;
  max_change_pct: string;
  min_minutes_between_changes: string;
  seats_weight: string;
  steps: string;
}

const toForm = (r: Rules): FormState => ({
  floor_switch_hours: String(r.floor_switch_hours),
  ceiling: String(r.ceiling),
  state_cap: r.state_cap == null ? '' : String(r.state_cap),
  max_change_pct: String(r.max_change_pct),
  min_minutes_between_changes: String(r.min_minutes_between_changes),
  seats_weight: String(r.seats_weight),
  steps: r.fare_steps.join(', '),
});

/** Same checks as the API, so mistakes show before the request. The API's 422 messages still win. */
function validateRules(f: FormState): { input: RulesInput | null; errors: Record<string, string> } {
  const e: Record<string, string> = {};
  const num = (v: string) => (v.trim() === '' ? NaN : Number(v));
  const ceiling = num(f.ceiling);
  const pct = num(f.max_change_pct);
  const minutes = num(f.min_minutes_between_changes);
  const weight = num(f.seats_weight);
  const switchHours = num(f.floor_switch_hours);
  const cap = f.state_cap.trim() === '' ? null : Number(f.state_cap);
  const steps = parseFareSteps(f.steps);
  if (!(switchHours >= 0)) e.floor_switch_hours = 'Must be 0 or more.';
  if (!(ceiling > 0)) e.ceiling = 'Must be greater than 0.';
  if (cap !== null && !(cap > 0)) e.state_cap = 'Must be greater than 0, or empty for no cap.';
  if (!(pct > 0 && pct <= 100)) e.max_change_pct = 'Must be above 0 and at most 100.';
  if (!(minutes >= 0)) e.min_minutes_between_changes = 'Must be 0 or more.';
  if (!(weight >= 0)) e.seats_weight = 'Must be 0 or more.';
  const stepErrors = validateFareSteps(steps);
  if (stepErrors.length) e.fare_steps = stepErrors[0] ?? 'Invalid fare steps.';
  else if (ceiling < (steps[0] ?? 0)) e.ceiling = 'Ceiling must be at least the smallest fare step.';
  if (Object.keys(e).length) return { input: null, errors: e };
  return {
    input: {
      floor_switch_hours: switchHours,
      ceiling,
      state_cap: cap,
      max_change_pct: pct,
      min_minutes_between_changes: minutes,
      seats_weight: weight,
      fare_steps: steps,
      updated_by: null,
    },
    errors: e,
  };
}

const FIELDS: { key: keyof Omit<FormState, 'steps'>; label: string; hint?: string }[] = [
  {
    key: 'floor_switch_hours',
    label: 'Floor switch point (hours before departure)',
    hint: 'Average floor until then, marginal floor after.',
  },
  { key: 'ceiling', label: 'Ceiling (₹)' },
  { key: 'state_cap', label: 'State cap (₹, optional)', hint: 'Leave empty if there is none.' },
  { key: 'max_change_pct', label: 'Largest change per step (%)' },
  { key: 'min_minutes_between_changes', label: 'Shortest time between changes (minutes)' },
  { key: 'seats_weight', label: 'Seats weight (₹ per extra expected seat)' },
];

function RulesForm({ rules }: { rules: Rules }) {
  const { user } = useUser();
  const toast = useToast();
  const update = useUpdateRules();
  const [form, setForm] = useState<FormState>(() => toForm(rules));
  const [errors, setErrors] = useState<Record<string, string>>({});
  const readOnly = user.role !== 'admin';

  function submit(e: FormEvent) {
    e.preventDefault();
    const { input, errors: found } = validateRules(form);
    setErrors(found);
    if (!input) return;
    update.mutate(
      { ...input, updated_by: user.name },
      {
        onSuccess: (saved) => {
          setForm(toForm(saved));
          toast(`Saved as version ${saved.version}. Applies to the next suggestion.`);
        },
        onError: (err) =>
          setErrors(
            err instanceof ApiError
              ? { ...err.fields, form: err.message }
              : { form: 'Could not save the rules.' },
          ),
      },
    );
  }

  return (
    <form onSubmit={submit} className="card max-w-3xl space-y-4" noValidate>
      <div className="flex items-baseline justify-between">
        <h1 className="text-3xl font-semibold">Pricing rules</h1>
        <p className="text-xs text-slate-500">
          Version {rules.version} · updated by {rules.updated_by ?? 'unknown'} ·{' '}
          {formatDateTime(rules.updated_at)}
        </p>
      </div>
      {readOnly && (
        <p className="rounded bg-slate-100 p-2 text-slate-700">
          Read-only: only an admin can change the rules. Switch to the Admin user to edit.
        </p>
      )}
      <fieldset disabled={readOnly} className="grid grid-cols-2 gap-4">
        {FIELDS.map((f) => (
          <div key={f.key}>
            <label htmlFor={f.key} className="label">
              {f.label}
            </label>
            <input
              id={f.key}
              className="input"
              inputMode="decimal"
              value={form[f.key]}
              aria-invalid={!!errors[f.key]}
              onChange={(e) => setForm({ ...form, [f.key]: e.target.value })}
            />
            {f.hint && <p className="mt-0.5 text-[11px] text-slate-500">{f.hint}</p>}
            {errors[f.key] && (
              <p role="alert" className="text-xs text-red-700">
                {errors[f.key]}
              </p>
            )}
          </div>
        ))}
        <div className="col-span-2">
          <FareStepsEditor
            text={form.steps}
            onChange={(steps) => setForm({ ...form, steps })}
            disabled={readOnly}
            error={errors.fare_steps}
          />
        </div>
      </fieldset>
      {errors.form && !Object.keys(errors).some((k) => k !== 'form' && errors[k] === errors.form) && (
        <p role="alert" className="text-sm text-red-700">
          {errors.form}
        </p>
      )}
      {!readOnly && (
        <div className="flex items-center gap-3">
          <button type="submit" className="btn btn-primary" disabled={update.isPending}>
            {update.isPending ? 'Saving…' : 'Save as new version'}
          </button>
          <span className="text-xs text-slate-500">Saving adds a new version; old versions are kept.</span>
        </div>
      )}
    </form>
  );
}

export default function SettingsPage() {
  const q = useRules();
  return (
    <div className="space-y-6">
      <SectionState loading={q.isLoading} error={q.error} rows={6}>
        {q.data && <RulesForm key={q.data.version} rules={q.data} />}
      </SectionState>
      <OwnersEditor />
    </div>
  );
}
