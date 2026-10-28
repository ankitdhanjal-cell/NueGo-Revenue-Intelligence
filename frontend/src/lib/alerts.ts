import { useOwners } from '../api/hooks';
import { useUser } from './user';

/** Whose alerts to show by default: the signed-in person's own if they own a route, otherwise everyone's (''). */
export function useDefaultAlertOwner(): string {
  const { user } = useUser();
  const owners = useOwners().data?.items;
  return owners?.some((o) => o.owner_id === user.id) ? user.id : '';
}
