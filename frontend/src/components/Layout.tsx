import { NavLink, Outlet } from 'react-router-dom';
import { usePipelineStatus, useWarnings } from '../api/hooks';
import { useDefaultAlertOwner } from '../lib/alerts';
import { formatDateTime } from '../lib/format';
import { useUser } from '../lib/user';

const NAV = [
  { to: '/', label: 'Services to review', end: true },
  { to: '/warnings', label: 'Alerts' },
  { to: '/totals', label: 'Money summary' },
  { to: '/fare-predictor', label: 'Fare checker' },
  { to: '/settings', label: 'Pricing rules' },
];

export default function Layout() {
  const { user, users, switchUser } = useUser();
  // In-app only: the badge counts the signed-in person's alerts if they own a route, otherwise everyone's.
  const mine = useDefaultAlertOwner();
  const alerts = useWarnings(mine || undefined).data?.items.length ?? 0;
  const run = usePipelineStatus().data?.last_run;
  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 flex h-screen w-60 shrink-0 flex-col border-r border-slate-300 bg-white px-5 py-6">
        <div className="mb-8">
          <div className="font-serif text-2xl font-bold leading-none text-brand-700">NueGo</div>
          <div className="mt-1 text-xs uppercase tracking-widest text-slate-500">Revenue desk</div>
        </div>
        <nav aria-label="Main" className="flex flex-1 flex-col gap-0.5">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.end}
              className={({ isActive }) =>
                `-ml-5 flex items-center justify-between border-l-2 py-2 pl-[18px] pr-2 ${isActive ? 'border-brand-700 font-semibold text-brand-700' : 'border-transparent text-slate-700 hover:bg-slate-100'}`
              }
            >
              {n.label}
              {n.to === '/warnings' && alerts > 0 && (
                <span
                  aria-label={mine ? `${alerts} alerts for you` : `${alerts} alerts`}
                  className="rounded-full bg-bad px-1.5 text-xs font-semibold text-white"
                >
                  {alerts}
                </span>
              )}
            </NavLink>
          ))}
        </nav>
        <p className={`mb-4 text-xs ${run?.status === 'failed' ? 'text-bad' : 'text-slate-500'}`}>
          {!run
            ? 'Data refresh not recorded yet'
            : `${run.status === 'failed' ? 'Last data refresh failed' : 'Data refreshed'} ${formatDateTime(run.finished_at)}`}
        </p>
        <div>
          <label htmlFor="user" className="label text-xs text-slate-500">
            Signed in as
          </label>
          <select id="user" className="input" value={user.id} onChange={(e) => switchUser(e.target.value)}>
            {users.map((u) => (
              <option key={u.id} value={u.id}>
                {u.name} ({u.role})
              </option>
            ))}
          </select>
        </div>
      </aside>
      <div className="min-w-0 flex-1">
        <main className="mx-auto max-w-[1180px] px-10 py-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
