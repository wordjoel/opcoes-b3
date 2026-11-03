/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { Regime } from '../types';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const EMPTY = '—';

export function formatCurrency(value: number | null | undefined) {
  if (value === null || value === undefined) return EMPTY;
  return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value);
}

/** Para ganho e perda, em que null significa sem limite. */
export function formatLimit(value: number | null) {
  return value === null ? 'Ilimitado' : formatCurrency(value);
}

export function formatNumber(value: number | null | undefined, digits = 2) {
  if (value === null || value === undefined) return EMPTY;
  return value.toLocaleString('pt-BR', { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

export function formatCompact(value: number | null | undefined) {
  if (value === null || value === undefined) return EMPTY;
  return new Intl.NumberFormat('pt-BR', { notation: 'compact', maximumFractionDigits: 1 }).format(value);
}

/** Valor em decimal: 0,25 vira 25,0%. */
export function formatRatio(value: number | null | undefined, digits = 1) {
  if (value === null || value === undefined) return EMPTY;
  return `${(value * 100).toLocaleString('pt-BR', { minimumFractionDigits: digits, maximumFractionDigits: digits })}%`;
}

/** Valor já em porcentagem, com sinal. */
export function formatChange(value: number | null | undefined) {
  if (value === null || value === undefined) return EMPTY;
  return `${value > 0 ? '+' : ''}${value.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%`;
}

/** "2026-10-30" vira "30/10/2026", sem passar por fuso. */
export function formatDay(day: string | null | undefined) {
  if (!day) return EMPTY;
  const [year, month, date] = day.split('-');
  return `${date}/${month}/${year}`;
}

export function formatMoment(moment: string | null | undefined) {
  if (!moment) return EMPTY;
  return new Date(moment).toLocaleString('pt-BR', {
    timeZone: 'America/Sao_Paulo',
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export const TREND_LABEL = { UP: 'Alta', DOWN: 'Baixa' } as const;

export const REGIME_LABEL: Record<Regime, string> = {
  BULL: 'Alta',
  BEAR: 'Baixa',
  SIDEWAYS: 'Lateral',
  HIGH_VOL: 'Vol cara',
  UNCERTAIN: 'Indefinido',
};
