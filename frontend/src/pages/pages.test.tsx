import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes } from 'react-router-dom';
import { afterEach, describe, expect, it } from 'vitest';
import DecisionButtons from '../components/DecisionButtons';
import { RECORDED_MESSAGE } from '../lib/labels';
import type { Suggestion } from '../api/types';
import Layout from '../components/Layout';
import OwnersEditor from '../components/settings/OwnersEditor';
import { state } from '../test/handlers';
import { renderWithProviders } from '../test/utils';
import DeskPage from './DeskPage';
import FarePredictorPage from './FarePredictorPage';
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

  it('opens a quick-look panel from a row, with a link to the full review', async () => {
    renderWithProviders(<DeskPage />);
    const rows = await screen.findAllByRole('row');
    await userEvent.click(rows[1] as HTMLElement);
    const panel = await screen.findByRole('dialog', { name: 'Delhi → Shimla' });
    expect(within(panel).getByText('12.2 seats behind')).toBeInTheDocument();
    expect(await within(panel).findByText('₹400')).toBeInTheDocument();
    expect(within(panel).getByRole('link', { name: 'Open full review' })).toHaveAttribute(
      'href',
      '/services/S-SLOW',
    );
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

  it('shows who owns the route, and everyone’s alerts when the signed-in person owns none', async () => {
    state.owners.R003 = 'admin';
    renderWithProviders(<WarningsPage />);
    const row = (await screen.findByRole('link', { name: 'Delhi → Shimla · 08:10' })).closest(
      'tr',
    ) as HTMLElement;
    expect(within(row).getByText('Admin')).toBeInTheDocument();
    expect(screen.getByLabelText(/show alerts for/i)).toHaveValue('');
  });

  it('starts on my own routes when I own one, and filters by person', async () => {
    state.owners.R003 = 'analyst-1';
    renderWithProviders(<WarningsPage />);
    expect(await screen.findByRole('link', { name: 'Delhi → Shimla · 08:10' })).toBeInTheDocument();
    expect(screen.getByLabelText(/show alerts for/i)).toHaveValue('analyst-1');
    await userEvent.selectOptions(screen.getByLabelText(/show alerts for/i), 'admin');
    expect(await screen.findByText(/nothing needs attention on this person/i)).toBeInTheDocument();
  });
});

describe('Sidebar', () => {
  it('counts everyone’s alerts when I own no route', async () => {
    renderWithProviders(<Layout />);
    expect(await screen.findByLabelText('1 alerts')).toBeInTheDocument();
    expect(await screen.findByText(/Data refreshed 28 Oct 2026/)).toBeInTheDocument();
  });

  it('says the alerts are mine when I own the route', async () => {
    state.owners.R003 = 'analyst-1';
    renderWithProviders(<Layout />);
    expect(await screen.findByLabelText('1 alerts for you')).toBeInTheDocument();
  });
});

describe('Route owners', () => {
  afterEach(() => localStorage.removeItem('userId'));

  it('is read-only for an analyst', async () => {
    renderWithProviders(<OwnersEditor />);
    expect(await screen.findByLabelText('Owner of Delhi → Shimla')).toBeDisabled();
    expect(screen.getByText(/only an admin can change this/i)).toBeInTheDocument();
  });

  it('lets an admin assign an owner', async () => {
    localStorage.setItem('userId', 'admin');
    renderWithProviders(<OwnersEditor />);
    const select = await screen.findByLabelText('Owner of Delhi → Shimla');
    await waitFor(() => expect(select).toBeEnabled());
    await userEvent.selectOptions(select, 'analyst-1');
    expect(await screen.findByText('Delhi → Shimla now belongs to Pricing analyst 1.')).toBeInTheDocument();
    expect(state.owners.R003).toBe('analyst-1');
  });
});

function renderReview(id: string, query = '') {
  return renderWithProviders(
    <Routes>
      <Route path="/services/:id" element={<ServicePage />} />
    </Routes>,
    `/services/${id}${query}`,
  );
}

describe('Review page', () => {
  it('shows the model prediction as a range next to the suggested fare, and the decision buttons', async () => {
    renderReview('S-OK');
    expect(await screen.findByText('₹400 (₹330–₹470)')).toBeInTheDocument();
    expect(screen.getByText('Suggested fare, inside your pricing rules')).toBeInTheDocument();
    expect(screen.getByText('Departs 25 Jan 2023, 08:10 AM', { exact: false })).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: 'Approve' })).toBeInTheDocument();
    expect(screen.getByText('4.2 (900 ratings)')).toBeInTheDocument();
    expect(screen.getByText(/FlixBus/)).toHaveTextContent('FlixBus ₹360, 20 min earlier');
  });

  it('shows the same-weekday trend on the Money tab', async () => {
    renderReview('S-OK', '?tab=money');
    const table = (await screen.findByRole('heading', { name: 'Same weekday, last 8 weeks' })).closest(
      'section',
    );
    expect(await within(table as HTMLElement).findByText('62.5%')).toBeInTheDocument();
    expect(within(table as HTMLElement).getByText('28 Dec 2022')).toBeInTheDocument();
  });

  it('says why no rival is shown on the Competitors tab, and still shows the route rating', async () => {
    renderReview('S-OK', '?tab=rivals');
    expect(
      await screen.findByText(/nearest rival departure on this route is 3 h 20 min away/),
    ).toBeInTheDocument();
    expect(screen.getByText(/Route rating: 4.2 \(940 ratings\)/)).toHaveTextContent('Our fare: ₹875');
    const row = screen.getByRole('row', { name: /HRTC/ });
    expect(row).toHaveTextContent('₹820');
    expect(row).toHaveTextContent('after our seats were counted');
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

describe('Fare checker', () => {
  it('asks for route, date, time, seats left and holiday, and shows the fare range', async () => {
    renderWithProviders(<FarePredictorPage />);
    expect(screen.queryByLabelText(/air conditioning/i)).not.toBeInTheDocument();
    await screen.findByRole('option', { name: 'Delhi → Shimla' });
    await userEvent.selectOptions(screen.getByLabelText('Holiday'), 'Holiday');
    await userEvent.click(screen.getByRole('button', { name: 'Check fare' }));
    expect(await screen.findByText('₹640 (₹594–₹686)')).toBeInTheDocument();
    expect(screen.getByText(/20 seats left, holiday$/)).toBeInTheDocument();
  });
});
