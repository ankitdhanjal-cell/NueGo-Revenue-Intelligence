const API_BASE = '/api/v1';

let userId = 'u1';
export function setApiUser(id: string): void {
  userId = id;
}

export class ApiError extends Error {
  status: number;
  fields: Record<string, string>;
  constructor(status: number, message: string, fields: Record<string, string> = {}) {
    super(message);
    this.status = status;
    this.fields = fields;
  }
}

interface ValidationItem {
  loc?: (string | number)[];
  msg?: string;
}

function readError(status: number, body: unknown): ApiError {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === 'string') return new ApiError(status, detail);
  if (Array.isArray(detail)) {
    const fields: Record<string, string> = {};
    const lines = (detail as ValidationItem[]).map((d) => {
      const field = String(d.loc?.[d.loc.length - 1] ?? 'request');
      const msg = (d.msg ?? 'Invalid value').replace(/^Value error, /, '');
      fields[field] = msg;
      return msg;
    });
    return new ApiError(status, lines.join('; '), fields);
  }
  return new ApiError(status, `Request failed (${status})`);
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', 'X-User-Id': userId, ...(init.headers ?? {}) },
  });
  const body: unknown = await res.json().catch(() => null);
  if (!res.ok) throw readError(res.status, body);
  return body as T;
}

export function qs(params: Record<string, string | number | undefined | null>): string {
  const p = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') p.set(k, String(v));
  });
  const s = p.toString();
  return s ? `?${s}` : '';
}
