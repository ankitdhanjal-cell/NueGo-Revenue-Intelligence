import { createContext, useContext, useMemo, useState, type ReactNode } from 'react';
import { setApiUser } from '../api/client';
import { useUsers } from '../api/hooks';
import type { User } from '../api/types';
import SectionState from '../components/SectionState';

interface UserContextValue {
  user: User;
  users: readonly User[];
  switchUser: (id: string) => void;
}

const UserContext = createContext<UserContextValue | null>(null);

function savedId(): string | null {
  try {
    return localStorage.getItem('userId');
  } catch {
    return null;
  }
}

/** Loads the people who can sign in from the API (auth stub) and remembers the choice in this browser. */
export function UserProvider({ children }: { children: ReactNode }) {
  const q = useUsers();
  const users = useMemo(() => q.data?.items ?? [], [q.data]);
  const [chosen, setChosen] = useState<string | null>(savedId);
  const user = users.find((u) => u.id === chosen) ?? users[0];
  if (user) setApiUser(user.id);

  const value = useMemo<UserContextValue | null>(
    () =>
      user
        ? {
            user,
            users,
            switchUser: (id) => {
              setApiUser(id);
              try {
                localStorage.setItem('userId', id);
              } catch {
                /* storage may be blocked; the switch still works for this session */
              }
              setChosen(id);
            },
          }
        : null,
    [user, users],
  );

  if (!value) {
    return (
      <div className="p-10">
        <SectionState
          loading={q.isLoading}
          error={q.error}
          empty={!q.isLoading && users.length === 0}
          emptyText="No users are set up."
        >
          {null}
        </SectionState>
      </div>
    );
  }
  return <UserContext.Provider value={value}>{children}</UserContext.Provider>;
}

export function useUser(): UserContextValue {
  const ctx = useContext(UserContext);
  if (!ctx) throw new Error('useUser must be used inside UserProvider');
  return ctx;
}
