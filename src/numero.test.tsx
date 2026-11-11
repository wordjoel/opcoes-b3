import { describe, expect, it } from 'vitest';
import { numeroOuNulo, parseNumeroBR } from './lib/numero';

const valor = (raw: string) => {
  const r = parseNumeroBR(raw);
  if (!r.ok) throw new Error(`esperava valor para "${raw}", veio: ${r.reason}`);
  return r.value;
};

describe('parseNumeroBR', () => {
  it('aceita os exemplos do roteiro', () => {
    expect(valor('17,50')).toBe(17.5);
    expect(valor('17.50')).toBe(17.5);
    expect(valor('R$ 1.234,56')).toBe(1234.56);
    expect(valor('1234.56')).toBe(1234.56);
    expect(valor('0,35')).toBe(0.35);
    expect(valor('0.35')).toBe(0.35);
  });

  it('aceita milhar com vírgula decimal e formato americano', () => {
    expect(valor('1.234.567,89')).toBe(1234567.89);
    expect(valor('1,234,567.89')).toBe(1234567.89);
    expect(valor('12.345,6')).toBe(12345.6);
  });

  it('aceita inteiros, sinal e espaços', () => {
    expect(valor('1234')).toBe(1234);
    expect(valor(' -2,5 ')).toBe(-2.5);
    expect(valor('US$ 10')).toBe(10);
    expect(valor(',5')).toBe(0.5);
  });

  it('aceita número já numérico', () => {
    expect(parseNumeroBR(3.2)).toEqual({ ok: true, value: 3.2 });
    expect(parseNumeroBR(Number.NaN).ok).toBe(false);
  });

  it('recusa milhar sem separador claro, para não errar por mil', () => {
    for (const raw of ['1.234', '12.345', '1.234.567']) {
      const r = parseNumeroBR(raw);
      expect(r.ok).toBe(false);
      if (!r.ok) expect(r.reason).toMatch(/milhar ou decimal/);
    }
  });

  it('recusa entradas inválidas', () => {
    for (const raw of ['', '   ', 'abc', '1,2,3', '1..2', '12a', '--1', '1,', '.', 'R$']) {
      expect(parseNumeroBR(raw).ok, raw).toBe(false);
    }
  });

  it('recusa milhar fora do padrão', () => {
    expect(parseNumeroBR('1.23,45').ok).toBe(false);
    expect(parseNumeroBR('1,2345.67').ok).toBe(false);
  });

  it('numeroOuNulo devolve null quando não dá para ler', () => {
    expect(numeroOuNulo('')).toBeNull();
    expect(numeroOuNulo('1.234')).toBeNull();
    expect(numeroOuNulo('2,5')).toBe(2.5);
  });
});
