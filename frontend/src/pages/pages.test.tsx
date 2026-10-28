import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import DecisionButtons from '../components/DecisionButtons';
import { RECORDED_MESSAGE } from '../lib/labels';
import type { Suggestion } from '../api/types';
import { renderWithProviders } from '../test/utils';
import DeskPage from './DeskPage';
import ServicePage from './ServicePage';
import WarningsPage from './WarningsPage';

describe('Desk', () => {
  it('renders ranked rows in the API order with an absolute departure date', async () => {
    renderWithProviders(<DeskPage />);
    const rows = await screen.findAllByRole('row');
    expect(within(rows[1] as HTMLElement).getAllByRole('cell')[0]).toHaveTextContent('1');
    expect(within(rows[1] as HTMLElement).getByText('Delhi → Shimla')).toBeInTheDocument();
    expect(within(rows[1] as HTMLElement).getByText('25 Jan 2023')).toBeInTheDocument();
    expect(await screen.findByText('services in this view')).toBeInTheDocument();
  });

  it('puts a cost-missing service in its own section with no rank', async () => {
    renderWithProviders(<DeskPage />);
    const heading = await screen.findByRole('heading', { name: 'Cannot be ranked yet' });
    const row = within(heading.closest('section') as HTMLElement).getAllByRole('row')[1] as HTMLElement;
    expect(within(row).getAllByRole('cell')[0]).toHaveTextContent('—');
    expect(within(row).getByText(/Cost missing/)).toBeInTheDocument();
  });

  it('keeps cancelled services in a collapsed section', async () => {
    renderWithProviders(<DeskPage />);
    expect(await screen.findByRole('button', { name: /show cancelled services/i })).toHaveAttribute(
      'aria-expanded',
      'false',
    );
  });

  it('says so, and offers the departed services, when a window is empty', async () => {
    renderWithProviders(<DeskPage />, '/?window=today');
    expect(await screen.findByText('No services in this window.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'See services that already departed' })).toBeInTheDocument();
  });
});

describe('Alerts', () => {
  it('lists services behind plan with a link to review them', async () => {
    renderWithProviders(<WarningsPage />);
    expect(await screen.findByRole('link', { name: 'Delhi → Shimla · 08:10' })).toHaveAttribute(
      'href',
      '/services/S-SLOW',
    );
  });
});

function renderReview(id: string) {
  return renderWithProviders(
    <Routes>
      <Route path="/services/:id" element={<ServicePage />} />
    </Routes>,
    `/services/${id}`,
  );
}

describe('Review page', () => {
  it('shows the model prediction as a range next to the suggested fare, and the decision buttons', async () => {
    renderReview('S-OK');
    expect(await screen.findByText('₹400 (₹330–₹470)')).toBeInTheDocument();
    expect(screen.getByText('Suggested fare, inside your pricing rules')).toBeInTheDocument();
    expect(screen.getByText('Departs 25 Jan 2023, 08:10 AM', { exact: false })).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: 'Approve' })).toBeInTheDocument();
  });

  it('explains a null suggestion, still shows the prediction and shows no decision buttons', async () => {
    renderReview('S-NOCOST');
    expect(await screen.findByText(/Cost is missing/)).toBeInTheDocument();
    expect(screen.getByText('₹400 (₹330–₹470)')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Approve' })).not.toBeInTheDocument();
  });
});

describe('Decision dialogs', () => {
  const suggestion = {
    suggestion_id: 'S-OK',
    service_id: 'S-OK',
    suggested_fare: 400,
    engine_fare: 385,
  } as Suggestion;

  it('requires a reason to reject and records the decision', async () => {
    const user = userEvent.setup();
    renderWithProviders(<DecisionButtons suggestion={suggestion} />);
    await user.click(await screen.findByRole('button', { name: 'Reject' }));
    await user.click(screen.getByRole('button', { name: 'Record decision' }));
    expect(await screen.findByText('A reason is required.')).toBeInTheDocument();
    await user.type(screen.getByLabelText(/Reason/), 'Festival demand');
    await user.click(screen.getByRole('button', { name: 'Record decision' }));
    expect(await screen.findByText(RECORDED_MESSAGE)).toBeInTheDocument();
  });

  it('does not let a blocked fare be selected', async () => {
    const user = userEvent.setup();
    renderWithProviders(<DecisionButtons suggestion={suggestion} />);
    await user.click(await screen.findByRole('button', { name: 'Change fare' }));
    const select = await screen.findByLabelText(/New fare/);
    await within(select).findAllByRole('option');
    const options = within(select).getAllByRole('option') as HTMLOptionElement[];
    expect(options.some((o) => o.disabled && o.textContent?.includes('Below the cost floor'))).toBe(true);
    expect(options.some((o) => !o.disabled && o.value !== '')).toBe(true);
  });

  it('shows who decided on a 409', async () => {
    const user = userEvent.setup();
    renderWithProviders(<DecisionButtons suggestion={suggestion} />);
    await user.click(await screen.findByRole('button', { name: 'Approve' }));
    await user.click(screen.getByRole('button', { name: 'Record decision' }));
    expect(await screen.findByText(RECORDED_MESSAGE)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Approve' }));
    await user.click(screen.getByRole('button', { name: 'Record decision' }));
    expect(await screen.findByText(/Already decided by Pricing analyst 1/)).toBeInTheDocument();
  });
});
