/** O cliente não transforma resposta sem procedência em dado real. */
import { describe, expect, it } from 'vitest';
import { readEnvelope } from './services/api';

describe('validação do envelope no cliente', () => {
  it('preserva o envelope informado pela API', () => {
    const envelope = readEnvelope({
      provenance: { source: 'b3', kind: 'EOD', collected_at: '2026-11-24T12:00:00Z', market_time: '2026-11-24T12:00:00Z', delay_seconds: 0 },
      data_status: 'ATRASADO',
      quality: { is_valid: true, issues: [] },
      missing: [],
      label: 'HISTÓRICO',
    });
    expect(envelope.data_status).toBe('ATRASADO');
    expect(envelope.label).toBe('HISTÓRICO');
    expect(envelope.provenance?.delay_seconds).toBe(0);
  });

  it('marca como INDISPONÍVEL quando a resposta não declara origem e qualidade', () => {
    const envelope = readEnvelope({ rows: [], generated_at: '2026-11-24T12:00:00Z' });
    expect(envelope.data_status).toBe('INDISPONIVEL');
    expect(envelope.label).toBe('INDISPONÍVEL');
    expect(envelope.provenance).toBeNull();
    expect(envelope.quality.issues[0].code).toBe('ENVELOPE_AUSENTE');
    expect(envelope.missing.length).toBeGreaterThan(0);
  });
});
