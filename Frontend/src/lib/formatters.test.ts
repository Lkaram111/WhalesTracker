import { formatUSD, formatPercent, formatTimeAgo } from './formatters';

describe('formatters', () => {
  it('formats USD with suffixes', () => {
    expect(formatUSD(123)).toBe('$123.00');
    expect(formatUSD(12_300)).toBe('$12.3K');
    expect(formatUSD(12_300_000)).toBe('$12.30M');
  });

  it('formats percent with sign', () => {
    expect(formatPercent(12.3456)).toBe('+12.35%');
    expect(formatPercent(-0.4)).toBe('-0.40%');
  });

  it('formats time ago for minutes and hours', () => {
    const now = new Date();
    const tenMinutesAgo = new Date(now.getTime() - 10 * 60 * 1000).toISOString();
    const twoHoursAgo = new Date(now.getTime() - 2 * 60 * 60 * 1000).toISOString();

    expect(formatTimeAgo(tenMinutesAgo)).toMatch(/10m ago/);
    expect(formatTimeAgo(twoHoursAgo)).toMatch(/2h ago/);
  });
});
