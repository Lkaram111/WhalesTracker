import type { Trade } from '@/types/api';

type Side = 'long' | 'short';

interface DirectionMeta {
  side: Side;
  isClose: boolean;
}

const directionMeta: Record<string, DirectionMeta> = {
  buy: { side: 'long', isClose: false },
  long: { side: 'long', isClose: false },
  deposit: { side: 'long', isClose: false },
  sell: { side: 'long', isClose: true },
  withdraw: { side: 'long', isClose: true },
  close_long: { side: 'long', isClose: true },
  short: { side: 'short', isClose: false },
  close_short: { side: 'short', isClose: true },
};

const defaultMeta: DirectionMeta = { side: 'long', isClose: false };

const normalizeDirection = (direction: Trade['direction']): string =>
  direction?.toString().toLowerCase();

const getDirectionMeta = (direction: Trade['direction']): DirectionMeta => {
  const normalized = normalizeDirection(direction);
  return directionMeta[normalized] || defaultMeta;
};

const directionBucket = (direction: Trade['direction']): string => {
  const normalized = normalizeDirection(direction);
  if (normalized === 'close_short') return 'close_short';
  if (normalized === 'close_long' || normalized === 'sell' || normalized === 'withdraw') {
    return 'close_long';
  }
  if (normalized === 'short') return 'short';
  return 'long';
};

const parseBaseAmount = (trade: Trade): number | null => {
  if (trade.amount_base !== null && trade.amount_base !== undefined) {
    const parsed = Number(trade.amount_base);
    if (!Number.isNaN(parsed)) {
      return Math.abs(parsed);
    }
  }
  const candidatePrice =
    trade.open_price_usd ?? trade.close_price_usd ?? trade.price_usd ?? null;
  if (candidatePrice && candidatePrice !== 0) {
    const estimate = trade.value_usd / candidatePrice;
    if (Number.isFinite(estimate)) {
      return Math.abs(estimate);
    }
  }
  return null;
};

const pickPrice = (trade: Trade, size: number | null): number | null => {
  const directPrice =
    trade.open_price_usd ?? trade.close_price_usd ?? trade.price_usd ?? null;
  if (directPrice !== null && Number.isFinite(directPrice)) {
    return directPrice;
  }
  if (size && size !== 0) {
    const inferred = trade.value_usd / size;
    return Number.isFinite(inferred) ? inferred : null;
  }
  return null;
};

const priceCloseEnough = (
  a: number | null,
  b: number | null,
  tolerancePct: number
): boolean => {
  if (a === null || b === null) return true;
  if (a === 0 || b === 0) return true;
  const diff = Math.abs(a - b) / Math.abs(a);
  return diff <= tolerancePct;
};

const computeExposureByTrade = (trades: Trade[]) => {
  const exposure: Record<string, { long: number; short: number }> = {};
  const result = new Map<string, { after: number; side: Side }>();

  const chronological = [...trades].sort(
    (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
  );

  chronological.forEach((trade) => {
    const meta = getDirectionMeta(trade.direction);
    const key = trade.base_asset || 'unknown';
    const size = parseBaseAmount(trade) ?? 0;
    const current = exposure[key] || { long: 0, short: 0 };
    const before = current[meta.side];
    const delta = meta.isClose ? -size : size;
    const after = Math.max(before + delta, 0);
    current[meta.side] = after;
    exposure[key] = current;
    result.set(trade.id, { after, side: meta.side });
  });

  return result;
};

export type AggregatedTrade = Trade & {
  groupedCount?: number;
  groupedIds?: string[];
  aggregatedAmountBase?: number | null;
  openedAmountBase?: number;
  closedAmountBase?: number;
  stillOpenAfter?: number | null;
};

interface AggregateOptions {
  windowMs?: number;
  priceTolerancePct?: number;
}

export const aggregateTrades = (
  trades: Trade[],
  options?: AggregateOptions
): AggregatedTrade[] => {
  const windowMs = options?.windowMs ?? 60_000;
  const priceTolerancePct = options?.priceTolerancePct ?? 0.002;
  const exposureByTrade = computeExposureByTrade(trades);

  const sorted = [...trades].sort(
    (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
  );

  const groups: Array<
    AggregatedTrade & {
      _ts: number;
      _price: number | null;
      _priceWeight: number;
      _valueSum: number;
      _directionBucket: string;
      _pnlSum: number;
      _hasPnl: boolean;
    }
  > = [];

  sorted.forEach((trade) => {
    const ts = new Date(trade.timestamp).getTime();
    const size = parseBaseAmount(trade);
    const meta = getDirectionMeta(trade.direction);
    const bucket = directionBucket(trade.direction);
    const price = pickPrice(trade, size);

    const match = groups.find(
      (g) =>
        g.base_asset === trade.base_asset &&
        g.chain === trade.chain &&
        g.source === trade.source &&
        g._directionBucket === bucket &&
        Math.abs(ts - g._ts) <= windowMs &&
        priceCloseEnough(price, g._price, priceTolerancePct)
    );

    const openSize = !meta.isClose && size !== null ? size : 0;
    const closeSize = meta.isClose && size !== null ? size : 0;

    if (match) {
      match.groupedCount = (match.groupedCount || 1) + 1;
      match.groupedIds = match.groupedIds ? [...match.groupedIds, trade.id] : [match.id, trade.id];
      match.value_usd += trade.value_usd;
      match.aggregatedAmountBase =
        match.aggregatedAmountBase === null || size === null
          ? match.aggregatedAmountBase ?? null
          : (match.aggregatedAmountBase ?? 0) + size;
      match.openedAmountBase = (match.openedAmountBase ?? 0) + openSize;
      match.closedAmountBase = (match.closedAmountBase ?? 0) + closeSize;
      match._valueSum += Math.abs(trade.value_usd);
      if (match.platform !== trade.platform) {
        match.platform = 'Multiple';
      }

      if (trade.pnl_usd !== null && trade.pnl_usd !== undefined) {
        match._pnlSum += trade.pnl_usd;
        match._hasPnl = true;
      }

      if (price !== null && size !== null && size > 0) {
        const totalWeight = match._priceWeight + size;
        const weightedPrice =
          ((match._price ?? price) * match._priceWeight + price * size) / totalWeight;
        match._price = weightedPrice;
        match._priceWeight = totalWeight;
        if (meta.isClose) {
          match.close_price_usd = weightedPrice;
        } else {
          match.open_price_usd = weightedPrice;
        }
      }
    } else {
      const exposure = exposureByTrade.get(trade.id);
      const hasPnl = trade.pnl_usd !== null && trade.pnl_usd !== undefined;
      groups.push({
        ...trade,
        groupedCount: 1,
        groupedIds: [trade.id],
        aggregatedAmountBase: size,
        openedAmountBase: openSize,
        closedAmountBase: closeSize,
        stillOpenAfter: exposure ? exposure.after : null,
        _ts: ts,
        _price: price,
        _priceWeight: size ?? 0,
        _valueSum: Math.abs(trade.value_usd),
        _directionBucket: bucket,
        _pnlSum: hasPnl ? trade.pnl_usd ?? 0 : 0,
        _hasPnl: hasPnl,
      });
    }
  });

  return groups.map(
    ({ _ts, _price, _priceWeight, _directionBucket, _valueSum, _pnlSum, _hasPnl, ...rest }) => {
      let pnlUsd = _hasPnl ? _pnlSum : null;
      let pnlPercent = _hasPnl && _valueSum > 0 ? (_pnlSum / _valueSum) * 100 : null;

      if (pnlUsd === null) {
        const meta = getDirectionMeta(rest.direction);
        const closed = rest.closedAmountBase ?? 0;
        if (
          meta.isClose &&
          closed > 0 &&
          rest.open_price_usd !== undefined &&
          rest.close_price_usd !== undefined &&
          rest.open_price_usd !== null &&
          rest.close_price_usd !== null
        ) {
          const delta =
            meta.side === 'long'
              ? rest.close_price_usd - rest.open_price_usd
              : rest.open_price_usd - rest.close_price_usd;
          pnlUsd = delta * closed;
          pnlPercent = _valueSum > 0 ? (pnlUsd / _valueSum) * 100 : null;
        }
      }

      return {
        ...rest,
        pnl_usd: pnlUsd,
        pnl_percent: pnlPercent,
      };
    }
  );
};
