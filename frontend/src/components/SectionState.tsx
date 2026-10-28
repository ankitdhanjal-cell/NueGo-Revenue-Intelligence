import type { ReactNode } from 'react';
import { ApiError } from '../api/client';

interface Props {
  loading: boolean;
  error: unknown;
  empty?: boolean;
  emptyText?: string;
  rows?: number;
  children: ReactNode;
}

/** One place for skeleton, error and empty states so every section behaves the same. */
export default function SectionState({
  loading,
  error,
  empty = false,
  emptyText = 'Nothing to show.',
  rows = 3,
  children,
}: Props) {
  if (loading) {
    return (
      <div role="status" aria-label="Loading" className="space-y-2">
        {Array.from({ length: rows }, (_, i) => (
          <div
            key={i}
            className="h-4 animate-pulse rounded bg-slate-200"
            style={{ width: `${90 - i * 15}%` }}
          />
        ))}
      </div>
    );
  }
  if (error) {
    const message = error instanceof ApiError ? error.message : 'Something went wrong. Try again.';
    const status = error instanceof ApiError ? ` (${error.status})` : '';
    return (
      <p role="alert" className="rounded bg-red-50 p-2 text-red-800">
        {message}
        {status}
      </p>
    );
  }
  if (empty) return <p className="text-slate-500">{emptyText}</p>;
  return <>{children}</>;
}
