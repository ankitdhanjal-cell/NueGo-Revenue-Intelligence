import { useState, type FormEvent } from 'react';
import { ApiError } from '../api/client';
import { useDecide, useWhatIf } from '../api/hooks';
import type { DecisionAction, Suggestion } from '../api/types';
import { validateDecision } from '../lib/decision';
import { formatINR } from '../lib/format';
import { RECORDED_MESSAGE, RULE_LABELS, WRONG_CATEGORIES } from '../lib/labels';
import Modal from './Modal';
import SectionState from './SectionState';
import { useToast } from './Toast';

const TITLES: Record<DecisionAction, string> = {
  approve: 'Approve suggested fare',
  change: 'Change fare',
  reject: 'Reject suggestion',
  wrong: 'Something looks wrong',
};

interface Props {
  action: DecisionAction;
  suggestion: Suggestion;
  onClose: () => void;
}

export default function DecisionDialog({ action, suggestion, onClose }: Props) {
  const toast = useToast();
  const decide = useDecide(suggestion);
  const whatIf = useWhatIf(suggestion.service_id);
  const [fare, setFare] = useState<number | null>(null);
  const [reason, setReason] = useState('');
  const [category, setCategory] = useState('');
  const [errors, setErrors] = useState<Record<string, string>>({});
  const rows = whatIf.data?.rows ?? [];
  const allowed = rows.filter((r) => r.blocked_by.length === 0).map((r) => r.fare);

  function submit(e: FormEvent) {
    e.preventDefault();
    if (decide.isPending) return;
    const found = validateDecision(action, { fare, reason, category }, allowed);
    setErrors(found);
    if (Object.keys(found).length > 0) return;
    decide.mutate(
      {
        action,
        fare: action === 'change' ? (fare ?? undefined) : undefined,
        reason: reason.trim() || undefined,
        category: category || undefined,
      },
      {
        onSuccess: () => {
          toast(RECORDED_MESSAGE);
          onClose();
        },
        onError: (err) => {
          if (err instanceof ApiError && err.status === 409) {
            toast(err.message, 'error');
            onClose();
          } else if (err instanceof ApiError) {
            setErrors({ ...err.fields, form: err.message });
          } else {
            setErrors({ form: 'Could not record the decision. Try again.' });
          }
        },
      },
    );
  }

  return (
    <Modal title={TITLES[action]} onClose={onClose}>
      <form onSubmit={submit} className="space-y-3" noValidate>
        {action === 'approve' && (
          <p>
            Approve <strong>{formatINR(suggestion.suggested_fare)}</strong> for this service? Engine fare is{' '}
            {formatINR(suggestion.engine_fare)}.
          </p>
        )}
        {action === 'change' && (
          <div>
            <label htmlFor="fare" className="label">
              New fare (allowed fare steps only)
            </label>
            <SectionState
              loading={whatIf.isLoading}
              error={whatIf.error}
              empty={rows.length === 0}
              emptyText="No fare steps available."
            >
              <select
                id="fare"
                className="input"
                value={fare ?? ''}
                onChange={(e) => setFare(e.target.value ? Number(e.target.value) : null)}
                aria-invalid={!!errors.fare}
              >
                <option value="">Select a fare…</option>
                {rows.map((r) => (
                  <option key={r.fare} value={r.fare} disabled={r.blocked_by.length > 0}>
                    {formatINR(r.fare)}
                    {r.blocked_by.length > 0
                      ? ` — blocked: ${r.blocked_by.map((c) => RULE_LABELS[c] ?? c).join(', ')}`
                      : ''}
                  </option>
                ))}
              </select>
            </SectionState>
          </div>
        )}
        {action === 'wrong' && (
          <div>
            <label htmlFor="category" className="label">
              Category
            </label>
            <select
              id="category"
              className="input"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              aria-invalid={!!errors.category}
            >
              <option value="">Select a category…</option>
              {WRONG_CATEGORIES.map((c) => (
                <option key={c.value} value={c.value}>
                  {c.label}
                </option>
              ))}
            </select>
          </div>
        )}
        <div>
          <label htmlFor="reason" className="label">
            Reason {action === 'approve' ? '(optional)' : '(required)'}
          </label>
          <textarea
            id="reason"
            className="input"
            rows={3}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            aria-invalid={!!errors.reason}
          />
        </div>
        {Object.entries(errors).map(([field, msg]) => (
          <p key={field} role="alert" className="text-sm text-red-700">
            {msg}
          </p>
        ))}
        <div className="flex justify-end gap-2 pt-1">
          <button type="button" className="btn" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="btn btn-primary" disabled={decide.isPending}>
            {decide.isPending ? 'Recording…' : 'Record decision'}
          </button>
        </div>
      </form>
    </Modal>
  );
}
