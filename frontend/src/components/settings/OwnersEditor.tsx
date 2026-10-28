import { ApiError } from '../../api/client';
import { useOwners, useSetOwner } from '../../api/hooks';
import { formatDateTime } from '../../lib/format';
import { useUser } from '../../lib/user';
import SectionState from '../SectionState';
import { useToast } from '../Toast';

/** Who gets the alerts for each corridor. Starts empty; only an admin can assign. */
export default function OwnersEditor() {
  const { user, users } = useUser();
  const q = useOwners();
  const setOwner = useSetOwner();
  const toast = useToast();
  const readOnly = user.role !== 'admin';
  const items = q.data?.items ?? [];

  function change(routeId: string, userId: string) {
    setOwner.mutate(
      { routeId, userId: userId || null },
      {
        onSuccess: (o) =>
          toast(
            o.owner_name
              ? `${o.route_label} now belongs to ${o.owner_name}.`
              : `${o.route_label} has no owner.`,
          ),
        onError: (err) => toast(err instanceof ApiError ? err.message : 'Could not save the owner.'),
      },
    );
  }

  return (
    <section className="card max-w-3xl" aria-labelledby="owners-h">
      <h2 id="owners-h" className="text-xl font-semibold">
        Who looks after each route
      </h2>
      <p className="mb-3 mt-1 text-slate-600">
        Alerts for a route go to its owner. {readOnly && 'Only an admin can change this.'}
      </p>
      <SectionState
        loading={q.isLoading}
        error={q.error}
        empty={items.length === 0}
        emptyText="No routes found."
      >
        <table className="w-full">
          <thead>
            <tr>
              {['Route', 'Owner', 'Assigned'].map((h) => (
                <th key={h} scope="col" className="px-2 py-1">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {items.map((o) => (
              <tr key={o.route_id} className="border-t border-slate-100">
                <td className="px-2 py-2">{o.route_label}</td>
                <td className="px-2 py-2">
                  <select
                    className="input"
                    aria-label={`Owner of ${o.route_label}`}
                    value={o.owner_id ?? ''}
                    disabled={readOnly || setOwner.isPending}
                    onChange={(e) => change(o.route_id, e.target.value)}
                  >
                    <option value="">No owner yet</option>
                    {users.map((u) => (
                      <option key={u.id} value={u.id}>
                        {u.name}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="px-2 py-2 text-slate-600">
                  {o.assigned_at ? `${o.assigned_by} · ${formatDateTime(o.assigned_at)}` : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </SectionState>
    </section>
  );
}
