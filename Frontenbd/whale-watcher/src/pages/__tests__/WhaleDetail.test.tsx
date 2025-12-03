import { fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import WhaleDetail from '../WhaleDetail';

const renderPage = () =>
  render(
    <MemoryRouter initialEntries={['/whales/ethereum/0xabc']}>
      <Routes>
        <Route path="/whales/:chain/:address" element={<WhaleDetail />} />
      </Routes>
    </MemoryRouter>
  );

describe('WhaleDetail page', () => {
  it('filters trades via tabs', () => {
    renderPage();

    const tab = screen.getByRole('tab', { name: /Hyperliquid/i });
    fireEvent.click(tab);

    // Only the hyperliquid trade should remain visible
    const table = screen.getByRole('table');
    const rows = table.querySelectorAll('tr');
    expect(rows.length).toBeGreaterThan(1);
    expect(table.querySelectorAll('td').length).toBeGreaterThan(0);
    expect(within(table).getAllByText('Hyperliquid').length).toBe(1);
  });
});
