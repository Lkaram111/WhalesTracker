import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

const mockWhaleDetail = jest.fn(() => <div>Whale Detail</div>);

jest.mock('../WhaleDetail', () => ({
  __esModule: true,
  default: (props: unknown) => {
    mockWhaleDetail(props);
    return <div>Whale Detail</div>;
  },
}));

const loadMyAccount = async (address?: string) => {
  jest.resetModules();
  jest.doMock('@/config', () => ({
    MY_HYPERLIQUID_ADDRESS: address ?? '',
  }));
  const module = await import('../MyAccount');
  jest.dontMock('@/config');
  return module.default;
};

describe('MyAccount page', () => {
  beforeEach(() => {
    mockWhaleDetail.mockClear();
  });

  it('shows empty state when no address is configured', async () => {
    const MyAccount = await loadMyAccount('');

    render(
      <MemoryRouter>
        <MyAccount />
      </MemoryRouter>
    );

    expect(screen.getByText(/HYPERLIQUID_ADDRESS/i)).toBeInTheDocument();
    expect(mockWhaleDetail).not.toHaveBeenCalled();
  });

  it('renders personal account view when address is configured', async () => {
    const MyAccount = await loadMyAccount('0xmyaddress');

    render(
      <MemoryRouter initialEntries={['/me']}>
        <MyAccount />
      </MemoryRouter>
    );

    expect(screen.getByText(/My Hyperliquid Account/i)).toBeInTheDocument();
    expect(screen.getByText(/Whale Detail/i)).toBeInTheDocument();
    expect(mockWhaleDetail).toHaveBeenCalledWith(
      expect.objectContaining({
        chainOverride: 'hyperliquid',
        addressOverride: '0xmyaddress',
        hideBackLink: true,
      })
    );
  });
});
