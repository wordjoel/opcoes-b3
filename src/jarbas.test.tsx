/** Jarbas IA: conversa por texto e voz, contexto da estrutura e destaque das pernas. Voz e API simuladas. */
import { act, cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { Jarbas } from './components/Jarbas';
import { StrategyGuideCard } from './components/StrategyGuide';
import { JarbasContext, setJarbasContext, stopTour } from './lib/jarbasStore';
import { pickVoice, speakable } from './lib/voice';

const CONTEXT: JarbasContext = {
  symbol: 'PETR4', structure_key: 'call_butterfly', structure_name: 'Borboleta com call', market_date: '2026-11-03', spot: 40,
  expiry: '2026-12-18', business_days_to_expiry: 31, net_premium: 50, max_profit: 150, max_loss: 50, breakevens: [38.5, 41.5],
  probability_of_profit: 0.31, decision_status: 'INCOMPLETA', decision_reasons: [], decision_missing: ['custos não informados'], warnings: [],
  legs: [
    { symbol: 'PETRL420', action: 'SELL', kind: 'CALL', strike: 40, quantity: 200, premium: 1 },
    { symbol: 'PETRL380', action: 'BUY', kind: 'CALL', strike: 38, quantity: 100, premium: 2.25 },
    { symbol: 'PETRL440', action: 'BUY', kind: 'CALL', strike: 42, quantity: 100, premium: 0.25 },
  ],
};

type Handler = (body: unknown) => { status?: number; body: unknown };
const STATUS = {
  available: true,
  providers: [{ name: 'openrouter', label: 'OpenRouter', model: 'nvidia/nemotron:free', paused: false }],
  usage: { day: '2026-11-07', questions: 3, requests: 3, failures: 0, tokens: 900, daily_limit: 200 },
  voice: { speak_replies: true, voice_name: null, voice_rate: 1 },
};
let routes: Record<string, Handler>;
const posted: unknown[] = [];
const synth = { speak: vi.fn(), cancel: vi.fn(), getVoices: vi.fn(() => [{ name: 'Luciana', lang: 'pt-BR' }, { name: 'Daniel', lang: 'pt-BR' }]) };

class FakeRecognition {
  static last: FakeRecognition | null = null;
  lang = '';
  interimResults = false;
  continuous = false;
  maxAlternatives = 1;
  onresult: ((event: unknown) => void) | null = null;
  onerror: ((event: unknown) => void) | null = null;
  onend: (() => void) | null = null;
  start = vi.fn(() => {
    FakeRecognition.last = this;
  });
  stop = vi.fn();
  abort = vi.fn();
}

beforeEach(() => {
  sessionStorage.clear();
  posted.length = 0;
  synth.speak.mockClear();
  synth.cancel.mockClear();
  routes = {
    'GET /api/jarbas/status': () => ({ body: STATUS }),
    'POST /api/jarbas/chat': (body) => {
      posted.push(body);
      return {
        body: {
          reply: 'Compre PETRL380 e PETRL440, depois venda 200 PETRL420.', provider: 'OpenRouter', model: 'nvidia/nemotron:free', attempts: [],
          conversation_id: 'c'.repeat(32), tools: [], usage: { questions: posted.length, daily_limit: 200 },
        },
      };
    },
  };
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    const method = init?.method ?? 'GET';
    const handler = routes[`${method} ${String(url).split('?')[0]}`];
    if (!handler) return new Response('{}', { status: 404 });
    const result = handler(init?.body ? JSON.parse(init.body as string) : null);
    return new Response(JSON.stringify(result.body), { status: result.status ?? 200 });
  }));
  vi.stubGlobal('speechSynthesis', synth);
  vi.stubGlobal('SpeechSynthesisUtterance', class { text: string; lang = ''; voice: unknown = null; rate = 1; pitch = 1; volume = 1; onstart: unknown; onend: unknown; constructor(text: string) { this.text = text; } });
  vi.stubGlobal('webkitSpeechRecognition', FakeRecognition);
  setJarbasContext(CONTEXT);
});

afterEach(() => {
  cleanup();
  stopTour();
  setJarbasContext(null);
  vi.unstubAllGlobals();
});

const openJarbas = async () => {
  render(
    <>
      <StrategyGuideCard item={{ key: CONTEXT.structure_key, net_premium: CONTEXT.net_premium, legs: CONTEXT.legs }} />
      <Jarbas />
    </>,
  );
  await userEvent.click(screen.getByRole('button', { name: 'Abrir o Jarbas IA' }));
  await screen.findByText(/Disponível · OpenRouter/);
};

describe('Jarbas IA', () => {
  it('conversa por texto com o contexto real da estrutura e mostra o provedor', async () => {
    await openJarbas();
    expect(screen.getByText('Borboleta com call')).toBeTruthy();
    await userEvent.type(screen.getByLabelText('Pergunta para o Jarbas'), 'Qual é o risco?');
    await userEvent.click(screen.getByRole('button', { name: 'Enviar' }));
    expect(await screen.findByText(/Compre PETRL380/)).toBeTruthy();
    expect(screen.getByText('via OpenRouter · nvidia/nemotron:free')).toBeTruthy();
    const body = posted[0] as { question: string; conversation_id?: string; context: JarbasContext };
    expect(body.question).toBe('Qual é o risco?');
    expect(body.conversation_id).toBeUndefined();
    expect(body.context.structure_key).toBe('call_butterfly');
    expect(body.context.legs).toHaveLength(3);
  });

  it('responde em voz e pode ser interrompido', async () => {
    await openJarbas();
    await userEvent.click(screen.getByRole('button', { name: 'Explicar esta estratégia' }));
    await screen.findByText(/Compre PETRL380/);
    expect(synth.speak).toHaveBeenCalled();
    const spoken = synth.speak.mock.calls.map(([utterance]) => (utterance as { text: string }).text).join(' ');
    expect(spoken).toMatch(/PETRL380/);
    // A voz masculina é escolhida quando existe.
    expect((synth.speak.mock.calls.at(-1)![0] as { voice: { name: string } }).voice.name).toBe('Daniel');
    await userEvent.click(screen.getByRole('button', { name: 'Interromper a fala' }));
    expect(synth.cancel).toHaveBeenCalled();
    await userEvent.click(screen.getByRole('button', { name: 'Desativar áudio' }));
    synth.speak.mockClear();
    await userEvent.click(screen.getByRole('button', { name: 'Qual é o risco?' }));
    await waitFor(() => expect(posted).toHaveLength(2));
    expect(synth.speak.mock.calls.filter(([u]) => (u as { text: string }).text !== '')).toHaveLength(0);
  });

  it('pergunta de montagem destaca as pernas em ordem: compras primeiro', async () => {
    await openJarbas();
    await userEvent.click(screen.getByRole('button', { name: 'Como faço a entrada?' }));
    const steps = screen.getByText('Montagem passo a passo').parentElement!.nextElementSibling!;
    await waitFor(() => expect(steps.querySelector('[aria-current="step"]')?.textContent).toMatch(/Compre 100 PETRL380/));
  });

  it('ouve a pergunta pelo microfone e envia o texto reconhecido', async () => {
    await openJarbas();
    await userEvent.click(screen.getByRole('button', { name: 'Falar com o Jarbas' }));
    const recognition = FakeRecognition.last!;
    expect(recognition.lang).toBe('pt-BR');
    act(() => {
      const result = Object.assign([{ transcript: 'Quando devo sair?' }], { isFinal: true });
      recognition.onresult!({ results: [result] });
      recognition.onend!();
    });
    await waitFor(() => expect(posted).toHaveLength(1));
    expect((posted[0] as { question: string }).question).toBe('Quando devo sair?');
  });

  it('avisa a permissão negada do microfone', async () => {
    await openJarbas();
    await userEvent.click(screen.getByRole('button', { name: 'Falar com o Jarbas' }));
    act(() => {
      FakeRecognition.last!.onerror!({ error: 'not-allowed' });
      FakeRecognition.last!.onend!();
    });
    expect(await screen.findByText(/Permissão do microfone negada/)).toBeTruthy();
  });

  it('sem provedor configurado, não finge que funciona', async () => {
    routes['GET /api/jarbas/status'] = () => ({ body: { ...STATUS, available: false, providers: [] } });
    render(<Jarbas />);
    await userEvent.click(screen.getByRole('button', { name: 'Abrir o Jarbas IA' }));
    expect(await screen.findByText('Nenhum provedor de IA configurado no servidor')).toBeTruthy();
    expect((screen.getByRole('button', { name: 'Explicar esta estratégia' }) as HTMLButtonElement).disabled).toBe(true);
  });

  it('mostra a falha de todos os provedores sem travar a conversa', async () => {
    routes['POST /api/jarbas/chat'] = () => ({ status: 503, body: { detail: { message: 'Nenhum provedor de IA respondeu agora. Tente de novo em instantes.', attempts: [] } } });
    await openJarbas();
    await userEvent.click(screen.getByRole('button', { name: 'Qual é o risco?' }));
    expect(await screen.findByText(/Nenhum provedor de IA respondeu agora/)).toBeTruthy();
    expect((screen.getByLabelText('Pergunta para o Jarbas') as HTMLInputElement).disabled).toBe(false);
  });

  it('sem internet, avisa e não envia', async () => {
    await openJarbas();
    act(() => {
      Object.defineProperty(navigator, 'onLine', { configurable: true, value: false });
      window.dispatchEvent(new Event('offline'));
    });
    expect(screen.getByText(/Sem conexão: o Jarbas precisa de internet/)).toBeTruthy();
    Object.defineProperty(navigator, 'onLine', { configurable: true, value: true });
  });
});

describe('Jarbas: histórico, consumo e configurações', () => {
  it('continua a conversa no servidor e mostra o consumo do dia', async () => {
    await openJarbas();
    expect(screen.getByText('3/200 hoje')).toBeTruthy();
    await userEvent.click(screen.getByRole('button', { name: 'Qual é o risco?' }));
    await screen.findByText(/Compre PETRL380/);
    await userEvent.click(screen.getByRole('button', { name: 'Qual é o lucro máximo?' }));
    await waitFor(() => expect(posted).toHaveLength(2));
    expect((posted[1] as { conversation_id: string }).conversation_id).toBe('c'.repeat(32));
    expect(await screen.findByText('2/200 hoje')).toBeTruthy();
  });

  it('reabre conversa do histórico vinda do banco', async () => {
    routes['GET /api/jarbas/conversations'] = () => ({
      body: { conversations: [{ id: 'd'.repeat(32), title: 'Como monto a borboleta?', created_at: '2026-11-07T10:00:00+00:00', updated_at: '2026-11-07T10:01:00+00:00', messages: 2 }] },
    });
    routes[`GET /api/jarbas/conversations/${'d'.repeat(32)}`] = () => ({
      body: {
        id: 'd'.repeat(32), title: 'Como monto a borboleta?', created_at: '', updated_at: '',
        messages: [
          { role: 'user', content: 'Como monto a borboleta?', provider: null, model: null, created_at: '' },
          { role: 'assistant', content: 'Resposta guardada no Turso.', provider: 'OpenRouter', model: 'm:free', created_at: '' },
        ],
      },
    });
    await openJarbas();
    await userEvent.click(screen.getByRole('button', { name: 'Histórico de conversas' }));
    await userEvent.click(await screen.findByRole('button', { name: /^Como monto a borboleta\?/ }));
    expect(await screen.findByText('Resposta guardada no Turso.')).toBeTruthy();
  });

  it('configurações: escolhe modelo gratuito e bloqueia pago sem autorização', async () => {
    const saved: unknown[] = [];
    routes['GET /api/jarbas/settings'] = () => ({
      body: { provider_order: ['openrouter', 'gemini'], openrouter_model: null, allow_paid: false, daily_limit: 200, retention_days: 90, speak_replies: true, voice_name: null, voice_rate: 1, updated_at: null, configured_providers: ['openrouter'] },
    });
    routes['GET /api/jarbas/models'] = () => ({
      body: {
        configured: true,
        chain: ['nvidia/nemotron:free'],
        models: [
          { id: 'nvidia/nemotron:free', name: 'N', context_length: 1, free: true, prompt_per_million: 0, completion_per_million: 0 },
          { id: 'openai/pago', name: 'P', context_length: 1, free: false, prompt_per_million: 2, completion_per_million: 8 },
        ],
      },
    });
    routes['PUT /api/jarbas/settings'] = (body) => {
      saved.push(body);
      return { body: { ...(body as object), updated_at: 'x', configured_providers: ['openrouter'] } };
    };
    await openJarbas();
    await userEvent.click(screen.getByRole('button', { name: 'Configurações do Jarbas' }));
    const select = (await screen.findByLabelText(/^Modelo do OpenRouter/)) as HTMLSelectElement;
    const paid = [...select.options].find((option) => option.value === 'openai/pago')!;
    expect(paid.disabled).toBe(true);
    expect(paid.textContent).toMatch(/Pago US\$ 2.00\/8.00/);
    await userEvent.selectOptions(select, 'nvidia/nemotron:free');
    await userEvent.click(screen.getByRole('button', { name: 'Salvar configurações do Jarbas' }));
    expect(await screen.findByText('Configurações salvas.')).toBeTruthy();
    expect(saved[0]).toMatchObject({ openrouter_model: 'nvidia/nemotron:free', allow_paid: false });
    expect(saved[0]).not.toHaveProperty('configured_providers');
  });

  it('nova conversa limpa a tela', async () => {
    await openJarbas();
    await userEvent.click(screen.getByRole('button', { name: 'Qual é o risco?' }));
    await screen.findByText(/Compre PETRL380/);
    await userEvent.click(screen.getByRole('button', { name: 'Nova conversa' }));
    expect(screen.queryByText(/Compre PETRL380/)).toBeNull();
  });

  it('sem estrutura na tela, sugere perguntas sobre o sistema', async () => {
    setJarbasContext(null);
    render(<Jarbas />);
    await userEvent.click(screen.getByRole('button', { name: 'Abrir o Jarbas IA' }));
    expect(await screen.findByRole('button', { name: 'Como está minha carteira?' })).toBeTruthy();
    expect(screen.getByText(/posso consultar mercado, travas e carteira/)).toBeTruthy();
  });
});

describe('voz', () => {
  it('prefere voz masculina pt-BR e cai para pt-BR neutra', () => {
    const voices = (names: string[]) => names.map((name) => ({ name, lang: 'pt-BR' })) as SpeechSynthesisVoice[];
    expect(pickVoice(voices(['Luciana', 'Felipe'])).voice?.name).toBe('Felipe');
    expect(pickVoice(voices(['Luciana', 'Google português do Brasil']))).toMatchObject({ male: false, voice: { name: 'Google português do Brasil' } });
    expect(pickVoice([{ name: 'Alex', lang: 'en-US' }] as SpeechSynthesisVoice[]).voice).toBeNull();
  });

  it('prepara o texto para leitura', () => {
    expect(speakable('**Débito** de R$ 1.250,50.')).toBe('Débito de 1250,50 reais.');
    expect(speakable('| Ordem | Strike |\n|---|---|\n| 1 | 38 |\n---')).not.toMatch(/[|-]{2,}/);
  });
});

describe('PWA', () => {
  it('avisa versão nova e só troca quando o usuário aceita', async () => {
    const { AppStatus } = await import('./components/AppStatus');
    render(<AppStatus />);
    const postMessage = vi.fn();
    act(() => {
      window.dispatchEvent(new CustomEvent('b3-update-ready', { detail: { waiting: { postMessage } } }));
    });
    await userEvent.click(await screen.findByRole('button', { name: 'Atualizar agora' }));
    expect(postMessage).toHaveBeenCalledWith('SKIP_WAITING');
  });

  it('oferece instalar quando o navegador permite', async () => {
    const { AppStatus } = await import('./components/AppStatus');
    render(<AppStatus />);
    const prompt = vi.fn(async () => {});
    act(() => {
      const event = Object.assign(new Event('beforeinstallprompt'), { prompt, userChoice: Promise.resolve({ outcome: 'accepted' }) });
      window.dispatchEvent(event);
    });
    await userEvent.click(await screen.findByRole('button', { name: 'Instalar app' }));
    expect(prompt).toHaveBeenCalled();
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Instalar app' })).toBeNull());
  });

  it('avisa quando está sem conexão', async () => {
    const { AppStatus } = await import('./components/AppStatus');
    render(<AppStatus />);
    act(() => {
      Object.defineProperty(navigator, 'onLine', { configurable: true, value: false });
      window.dispatchEvent(new Event('offline'));
    });
    expect(screen.getByText(/Sem conexão. Dados de mercado, login e o Jarbas precisam de internet/)).toBeTruthy();
    Object.defineProperty(navigator, 'onLine', { configurable: true, value: true });
  });
});
