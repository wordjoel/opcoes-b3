/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { AssetData, RobotState, Trend } from './types';

export const MOCK_ASSETS: AssetData[] = [
  { ticker: 'PETR4', price: 38.50, change: 1.2, volatility: 25, trend: Trend.BULLISH, volume: 150000000 },
  { ticker: 'VALE3', price: 65.20, change: -0.8, volatility: 22, trend: Trend.NEUTRAL, volume: 120000000 },
  { ticker: 'ITUB4', price: 32.10, change: 0.5, volatility: 18, trend: Trend.BULLISH, volume: 90000000 },
  { ticker: 'BBAS3', price: 28.45, change: 1.5, volatility: 20, trend: Trend.BULLISH, volume: 75000000 },
  { ticker: 'BBDC4', price: 14.80, change: -2.1, volatility: 30, trend: Trend.BEARISH, volume: 85000000 },
  { ticker: 'MGLU3', price: 2.15, change: -4.5, volatility: 65, trend: Trend.BEARISH, volume: 60000000 },
  { ticker: 'WEGE3', price: 42.10, change: 0.2, volatility: 19, trend: Trend.NEUTRAL, volume: 45000000 },
  { ticker: 'B3SA3', price: 11.20, change: -0.5, volatility: 28, trend: Trend.NEUTRAL, volume: 55000000 },
];

export const INITIAL_ROBOTS: RobotState[] = [
  { id: 'scanner', name: 'Robô Scanner', status: 'IDLE', message: 'Aguardando início...' },
  { id: 'trend', name: 'Robô de Tendência', status: 'IDLE', message: 'Aguardando dados...' },
  { id: 'volatility', name: 'Robô de Volatilidade', status: 'IDLE', message: 'Aguardando dados...' },
  { id: 'strategy', name: 'Robô de Estratégia', status: 'IDLE', message: 'Aguardando análise...' },
  { id: 'risk', name: 'Robô de Risco', status: 'IDLE', message: 'Aguardando estratégia...' },
];

export const COLORS = {
  bg: '#0F172A', // Navy Dark
  accent: '#38BDF8', // Sky Blue
  green: '#10B981',
  red: '#EF4444',
  text: '#F8FAFC',
  muted: '#94A3B8',
  card: '#1E293B'
};
