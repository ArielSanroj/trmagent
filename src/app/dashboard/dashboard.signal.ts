import { TradingSignal } from '../services/api.service';

export interface SignalState {
  signalClass: string;
  signalIcon: string;
  signalText: string;
  signalConfidence: number;
  expectedReturn: number;
  signalReason: string;
  canBuy: boolean;
}

export const resolveSignalState = (signal: TradingSignal | null): SignalState => {
  if (!signal) {
    return {
      signalClass: 'hold',
      signalIcon: '⏸️',
      signalText: 'ESPERAR',
      signalConfidence: 0,
      expectedReturn: 0,
      signalReason: 'Esperando datos del mercado...',
      canBuy: false
    };
  }

  const signalConfidence = Math.round(signal.confidence * 100);
  const expectedReturn = Number((signal.expected_return * 100).toFixed(2));
  const signalReason = signal.reasoning;
  const canBuy = signal.approved && signal.action === 'BUY_USD';

  switch (signal.action) {
    case 'BUY_USD':
      return {
        signalClass: 'buy',
        signalIcon: '🟢',
        signalText: 'COMPRAR USD',
        signalConfidence,
        expectedReturn,
        signalReason,
        canBuy
      };
    case 'SELL_USD':
      return {
        signalClass: 'sell',
        signalIcon: '🔴',
        signalText: 'VENDER USD',
        signalConfidence,
        expectedReturn,
        signalReason,
        canBuy
      };
    default:
      return {
        signalClass: 'hold',
        signalIcon: '🟡',
        signalText: 'MANTENER',
        signalConfidence,
        expectedReturn,
        signalReason,
        canBuy
      };
  }
};
