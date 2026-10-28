import type { FlagName } from '../api/types';

export const FLAG_LABELS: Record<FlagName, string> = {
  cost_missing: 'Cost missing',
  no_history: 'No history',
  low_confidence: 'Low confidence',
  rival_missing: 'No rival data',
  floor_missing: 'Floor fallback',
  sold_out: 'Sold out',
};

export const RULE_LABELS: Record<string, string> = {
  NOT_A_FARE_STEP: 'Not an allowed fare step',
  BELOW_FLOOR: 'Below the cost floor',
  ABOVE_CEILING: 'Above the ceiling',
  ABOVE_STATE_CAP: 'Above the state cap',
  STEP_TOO_LARGE: 'Change from current fare too large',
  TOO_SOON: 'Too soon after the last change',
  NO_FLOOR: 'No cost floor to check against',
};

export const BLOCKED_LABELS: Record<string, string> = {
  CANCELLED: 'Cancelled service: no suggestion.',
  COST_MISSING: 'Cost is missing, so there is no safe floor and no suggestion.',
  NO_FLOOR: 'No cost floor could be computed, so there is no suggestion.',
  NO_FARE_PREDICTION:
    'The model could not predict a fare (the coach type is unknown), so there is no suggestion.',
  NO_SEAT_FORECAST: 'No seat forecast for this service, so there is no suggestion.',
  NO_ALLOWED_FARE: 'No fare passes all the pricing rules.',
};

export const WRONG_CATEGORIES = [
  { value: 'pace_misread', label: 'Pace misread' },
  { value: 'rival_data_wrong', label: 'Rival data wrong' },
  { value: 'cost_wrong', label: 'Cost wrong' },
  { value: 'event_missed', label: 'Event missed' },
  { value: 'other', label: 'Other' },
];

export const RECORDED_MESSAGE = 'Recorded. Apply this fare in the pricing engine.';
