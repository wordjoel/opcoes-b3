/**
 * Leitura de números digitados pelo usuário, em padrão brasileiro ou americano.
 *
 * Regras, para evitar interpretações ambíguas:
 * - Com vírgula e ponto juntos, o último separador é o decimal: "1.234,56" e "1,234.56" valem 1234.56.
 * - Só vírgula: é decimal ("17,50" vale 17.5, "0,35" vale 0.35).
 * - Só ponto: é decimal, salvo se parecer milhar ("1.234" ou "1.234.567"), que é recusado.
 *   Nesse caso o usuário precisa escrever "1234" ou "1234,00", para não errar por um fator de mil.
 * - "R$", "US$" e espaços são ignorados.
 */

export type ParsedNumber = { ok: true; value: number; reason?: undefined } | { ok: false; reason: string; value?: undefined };

const EMPTY = 'Informe um valor.';
const INVALID = 'Use só números, com vírgula ou ponto decimal.';
const AMBIGUOUS = 'Não dá para saber se é milhar ou decimal. Escreva sem separador de milhar (1234) ou com vírgula decimal (1234,50).';

const BR_GROUPS = /^\d{1,3}(\.\d{3})+$/;

export function parseNumeroBR(raw: string | number | null | undefined): ParsedNumber {
  if (typeof raw === 'number') {
    return Number.isFinite(raw) ? { ok: true, value: raw } : { ok: false, reason: INVALID };
  }
  if (raw === null || raw === undefined) return { ok: false, reason: EMPTY };

  let text = String(raw).replace(/\s/g, '').replace(/^(R\$|US\$)/i, '');
  if (text === '') return { ok: false, reason: EMPTY };

  let sign = 1;
  if (text.startsWith('-') || text.startsWith('+')) {
    if (text.startsWith('-')) sign = -1;
    text = text.slice(1);
  }
  if (text === '') return { ok: false, reason: INVALID };

  const commas = (text.match(/,/g) ?? []).length;
  const dots = (text.match(/\./g) ?? []).length;
  let normalized: string;

  if (commas > 0 && dots > 0) {
    const lastComma = text.lastIndexOf(',');
    const lastDot = text.lastIndexOf('.');
    const decimalIsComma = lastComma > lastDot;
    const thousands = decimalIsComma ? '.' : ',';
    const cut = decimalIsComma ? lastComma : lastDot;
    const integerPart = text.slice(0, cut);
    const fraction = text.slice(cut + 1);
    const groups = integerPart.split(thousands);
    if (groups.length < 2 || groups.some((g, i) => (i === 0 ? !/^\d{1,3}$/.test(g) : !/^\d{3}$/.test(g)))) {
      return { ok: false, reason: INVALID };
    }
    if (!/^\d+$/.test(fraction)) return { ok: false, reason: INVALID };
    normalized = `${groups.join('')}.${fraction}`;
  } else if (commas > 1) {
    return { ok: false, reason: INVALID };
  } else if (commas === 1) {
    if (!/^\d*,\d+$/.test(text)) return { ok: false, reason: INVALID };
    normalized = text.replace(',', '.');
  } else if (dots > 1) {
    if (!BR_GROUPS.test(text)) return { ok: false, reason: INVALID };
    return { ok: false, reason: AMBIGUOUS };
  } else if (dots === 1) {
    const [integer, fraction] = text.split('.');
    if (/^\d{1,3}$/.test(integer) && /^\d{3}$/.test(fraction)) return { ok: false, reason: AMBIGUOUS };
    if (!/^\d*\.\d+$/.test(text)) return { ok: false, reason: INVALID };
    normalized = text;
  } else {
    if (!/^\d+$/.test(text)) return { ok: false, reason: INVALID };
    normalized = text;
  }

  const value = sign * Number(normalized);
  if (!Number.isFinite(value)) return { ok: false, reason: INVALID };
  return { ok: true, value };
}

/** Número salvo em texto de campo: 0.125 vira "0,125", que o parser lê sem ambiguidade. */
export function paraCampo(value: number): string {
  return String(value).replace('.', ',');
}

/** Valor ou null, para formulários que aceitam campo vazio. */
export function numeroOuNulo(raw: string): number | null {
  const parsed = parseNumeroBR(raw);
  return parsed.ok ? parsed.value : null;
}
