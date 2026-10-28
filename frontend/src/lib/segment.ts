/** Slot and days-to-go band, derived the same way the API derives them. */
export function slotOf(hour: number): 'morning' | 'afternoon' | 'evening' | 'night' {
  if (hour >= 5 && hour < 12) return 'morning';
  if (hour >= 12 && hour < 17) return 'afternoon';
  if (hour >= 17 && hour < 20) return 'evening';
  return 'night';
}

export function dtgBandOf(daysToGo: number): '0-3' | '3-7' | '7-14' | '14+' {
  if (daysToGo <= 3) return '0-3';
  if (daysToGo <= 7) return '3-7';
  if (daysToGo <= 14) return '7-14';
  return '14+';
}
