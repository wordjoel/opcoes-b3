/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

export enum Trend {
  BULLISH = 'bullish',
  BEARISH = 'bearish',
  NEUTRAL = 'neutral'
}

export enum StrategyType {
  BULL_CALL_SPREAD = 'Bull Call Spread',
  BEAR_PUT_SPREAD = 'Bear Put Spread',
  IRON_CONDOR = 'Iron Condor',
  STRADDLE = 'Straddle'
}

export interface Option {
  strike: number;
  premium: number;
  type: 'CALL' | 'PUT';
  expiry: string;
  ticker: string;
}

export interface Strategy {
  id: string;
  type: StrategyType;
  ticker: string;
  description: string;
  legs: {
    action: 'BUY' | 'SELL';
    option: Option;
  }[];
  maxProfit: number;
  maxLoss: number;
  probability: number;
  cost: number;
  stepByStep: string[];
}

export interface AssetData {
  ticker: string;
  price: number;
  change: number;
  volatility: number;
  trend: Trend;
  volume: number;
}

export interface RobotState {
  id: string;
  name: string;
  status: 'IDLE' | 'SCANNING' | 'ANALYZING' | 'EXECUTING' | 'ALERTING';
  message: string;
}
