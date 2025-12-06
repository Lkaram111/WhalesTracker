const rawMyHyperliquidAddress =
  typeof import.meta !== 'undefined' && typeof (import.meta as Record<string, unknown>).env !== 'undefined'
    ? (() => {
        const env = (import.meta as unknown as { env?: Record<string, unknown> }).env ?? {};
        return (
          env.HYPERLIQUID_ADDRESS ??
          env.VITE_HYPERLIQUID_ADDRESS ??
          env.VITE_MY_HYPERLIQUID_ADDRESS ??
          ''
        );
      })()
    : undefined;

export const MY_HYPERLIQUID_ADDRESS =
  typeof rawMyHyperliquidAddress === 'string' ? rawMyHyperliquidAddress.trim() : '';
