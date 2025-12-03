import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Whales from '../Whales';

describe('Whales page', () => {
  it('paginates results', () => {
    render(
      <MemoryRouter>
        <Whales />
      </MemoryRouter>
    );

    expect(screen.getByText(/Showing/i)).toHaveTextContent('1-5 of 8');

    const next = screen.getByLabelText(/Go to next page/i);
    fireEvent.click(next);

    expect(screen.getByText(/Showing/i)).toHaveTextContent('6-8 of 8');
    expect(screen.getByText(/Page/)).toHaveTextContent('Page 2 of 2');
  });
});
