import { formatTimeToGo } from '../lib/format';

interface Props {
  departure: string;
  /** The moment the numbers were taken. Defaults to the current time. */
  now?: string | Date;
}

export default function TimeToGo({ departure, now = new Date() }: Props) {
  const hours = (new Date(departure).getTime() - new Date(now).getTime()) / 3_600_000;
  return <span className="whitespace-nowrap tabular-nums">{formatTimeToGo(hours)}</span>;
}
