import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import CheckpointBar from './CheckpointBar';
import FlagBadges from './FlagBadges';
import Money from './Money';
import RangeValue from './RangeValue';
import TimeToGo from './TimeToGo';

describe('RangeValue', () => {
  it('always shows low and high next to mid', () => {
    render(<RangeValue range={{ low: 1234, mid: 5678, high: 91011 }} format="inr" />);
    expect(screen.getByText('₹5,678 (₹1,234–₹91,011)')).toBeInTheDocument();
  });
  it('shows a placeholder, never a bare number, when there is no range', () => {
    render(<RangeValue range={null} format="seats" missing="No history" />);
    expect(screen.getByText('No history')).toBeInTheDocument();
  });
});

describe('TimeToGo', () => {
  it('shows days and hours', () => {
    render(<TimeToGo departure="2026-05-03T14:00:00" now="2026-05-01T10:00:00" />);
    expect(screen.getByText('2 d 4 h')).toBeInTheDocument();
  });
  it('shows hours and minutes inside the last day', () => {
    render(<TimeToGo departure="2026-05-01T13:20:00" now="2026-05-01T10:00:00" />);
    expect(screen.getByText('3 h 20 m')).toBeInTheDocument();
  });
});

describe('Money and FlagBadges', () => {
  it('shows the missing label instead of ₹0', () => {
    render(<Money value={null} missing="Cost missing" />);
    expect(screen.getByText('Cost missing')).toBeInTheDocument();
  });
  it('uses plain labels for flags', () => {
    render(
      <FlagBadges
        flags={{ cost_missing: true, no_history: true, low_confidence: true, rival_missing: true }}
      />,
    );
    ['Cost missing', 'No history', 'Low confidence', 'No rival data'].forEach((t) =>
      expect(screen.getByText(new RegExp(t))).toBeInTheDocument(),
    );
  });
});

describe('CheckpointBar', () => {
  it('describes sold seats and the checkpoint range for screen readers', () => {
    render(<CheckpointBar sold={12} capacity={40} checkpoint={{ low: 8, mid: 15, high: 22 }} />);
    expect(screen.getByRole('img')).toHaveAttribute(
      'aria-label',
      '12 of 40 seats sold, checkpoint 15 (8–22)',
    );
  });
});
