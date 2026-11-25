import { describe, expect, it } from 'vitest';
import {
  TOOLS,
  byCategory,
  countByCategory,
  findTool,
  recommended,
  searchTools,
} from './lib/toolsCatalog';

describe('toolsCatalog', () => {
  it('contém os 82 recursos do catálogo', () => {
    expect(TOOLS).toHaveLength(82);
  });

  it('mantém ids únicos e sequenciais de 1 a 82', () => {
    const ids = TOOLS.map((tool) => tool.id);
    expect(new Set(ids).size).toBe(82);
    expect(Math.min(...ids)).toBe(1);
    expect(Math.max(...ids)).toBe(82);
  });

  it('filtra corretamente por categoria', () => {
    expect(byCategory('agentes')).toHaveLength(31);
    expect(byCategory('utilitarios')).toHaveLength(19);
    expect(byCategory('modelos')).toHaveLength(14);
    expect(byCategory('design')).toHaveLength(18);
  });

  it('a contagem por categoria corresponde aos filtros', () => {
    expect(countByCategory()).toEqual({
      agentes: 31,
      utilitarios: 19,
      modelos: 14,
      design: 18,
    });
  });

  it('localiza um recurso pelo id original', () => {
    expect(findTool(33)?.name).toBe('public-apis/public-apis');
    expect(findTool(61)?.name).toBe('opendatalab/MinerU');
    expect(findTool(999)).toBeUndefined();
  });

  it('busca por termo em nome ou nota', () => {
    const ids = searchTools('ocr').map((tool) => tool.id);
    expect(ids).toContain(61);
    expect(ids).toContain(64);
    expect(searchTools('   ')).toEqual([]);
  });

  it('retorna somente recomendações', () => {
    const list = recommended();
    expect(list.length).toBeGreaterThan(0);
    expect(list.every((tool) => tool.status === 'RECOMENDADO')).toBe(true);
  });
});
