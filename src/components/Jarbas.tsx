import { FormEvent, useEffect, useRef, useState } from 'react';
import { History, Mic, MicOff, Plus, Send, Settings, Square, Trash2, Volume2, VolumeX, X } from 'lucide-react';
import { api, ApiError, JarbasSettings, JarbasStatus, useResource } from '../services/api';
import { cn, formatMoment } from '../lib/utils';
import { startTour, stopTour, useJarbasState } from '../lib/jarbasStore';
import { canListen, canSpeak, Listening, listen, portugueseVoices, secureContext, speak, unlockSpeech } from '../lib/voice';

interface Message {
  role: 'user' | 'assistant' | 'notice';
  content: string;
  provider?: string | null;
  model?: string | null;
}

type View = 'chat' | 'history' | 'settings';
type Activity = 'idle' | 'listening' | 'thinking' | 'speaking';

const SUGGESTIONS_WITH_STRUCTURE = ['Explicar esta estratégia', 'Como faço a entrada?', 'Quando devo sair?', 'Qual é o risco?', 'Qual é o lucro máximo?', 'Compare com outra estrutura'];
const SUGGESTIONS_GENERAL = ['Quais oportunidades merecem atenção hoje?', 'Quais travas apresentam melhor retorno?', 'Quais grades estão defasadas?', 'Como está minha carteira?', 'Quais vencimentos estão próximos?'];

// Perguntas de montagem disparam o destaque das pernas no gráfico.
const ASSEMBLY = /mont|entrada|como fa[çc]o|pernas?|comprar|vender/i;
const CONVERSATION_KEY = 'jarbas-conversa-id';
const PROVIDER_LABEL: Record<string, string> = { openrouter: 'OpenRouter', gemini: 'Gemini', groq: 'Groq', custom: 'Personalizado' };
const ACTIVITY_LABEL: Record<Activity, string> = { idle: '', listening: 'Ouvindo...', thinking: 'Consultando e pensando...', speaking: 'Falando...' };

function readKey(key: string): string | null {
  try {
    return sessionStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeKey(key: string, value: string | null) {
  try {
    if (value) sessionStorage.setItem(key, value);
    else sessionStorage.removeItem(key);
  } catch {
    // Armazenamento bloqueado: a conversa continua no servidor, só não reabre sozinha.
  }
}

function JarbasAvatar({ active, activity = 'idle' }: { active: boolean; activity?: Activity }) {
  return (
    <svg viewBox="0 0 40 40" className={cn('w-9 h-9 shrink-0', activity !== 'idle' && 'animate-pulse')} aria-hidden="true">
      <circle cx="20" cy="20" r="19" fill="#191916" />
      <circle cx="20" cy="20" r="19" fill="none" stroke={activity === 'listening' ? '#a3231d' : active ? '#2f6b3a' : '#9b978e'} strokeWidth="2" />
      <text x="20" y="26" textAnchor="middle" fontSize="18" fontWeight="900" fill="#f3efe5" fontFamily="serif">
        J
      </text>
    </svg>
  );
}

export function Jarbas() {
  const [open, setOpen] = useState(false);
  const [view, setView] = useState<View>('chat');
  const { context } = useJarbasState();
  const status = useResource(open ? 'jarbas-status' : null, api.jarbasStatus);
  const [live, setLive] = useState<JarbasStatus | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(() => readKey(CONVERSATION_KEY));
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState('');
  const [activity, setActivity] = useState<Activity>('idle');
  const [audio, setAudio] = useState(true);
  const [online, setOnline] = useState(() => (typeof navigator === 'undefined' ? true : navigator.onLine));
  const stopSpeech = useRef<() => void>(() => {});
  const recognition = useRef<Listening | null>(null);
  const list = useRef<HTMLDivElement>(null);
  const loadedConversation = useRef<string | null>(null);

  useEffect(() => setLive(status.data), [status.data]);
  useEffect(() => {
    if (status.data) setAudio((status.data.voice?.speak_replies ?? true) && canSpeak());
  }, [status.data]);
  useEffect(() => writeKey(CONVERSATION_KEY, conversationId), [conversationId]);
  // Reabre a conversa da sessão a partir do banco, em qualquer aparelho.
  useEffect(() => {
    if (!open || !conversationId || loadedConversation.current === conversationId) return;
    loadedConversation.current = conversationId;
    api
      .jarbasConversation(conversationId)
      .then((found) => setMessages(found.messages.map((m) => ({ role: m.role, content: m.content, provider: m.provider, model: m.model }))))
      .catch(() => setConversationId(null));
  }, [open, conversationId]);
  useEffect(() => {
    list.current?.scrollTo?.({ top: list.current.scrollHeight });
  }, [messages, activity]);
  useEffect(() => {
    const update = () => setOnline(navigator.onLine);
    window.addEventListener('online', update);
    window.addEventListener('offline', update);
    return () => {
      window.removeEventListener('online', update);
      window.removeEventListener('offline', update);
    };
  }, []);
  useEffect(() => () => stopSpeech.current(), []);

  const available = live?.available ?? false;
  const busy = activity === 'thinking';
  const ready = online && available && !busy;
  const usage = live?.usage;

  const interrupt = () => {
    stopSpeech.current();
    stopSpeech.current = () => {};
    setActivity((current) => (current === 'speaking' ? 'idle' : current));
  };

  const notice = (content: string) => setMessages((current) => [...current, { role: 'notice', content }]);

  const ask = async (question: string) => {
    const text = question.trim();
    if (!text || !ready) return;
    unlockSpeech();
    interrupt();
    setMessages((current) => [...current, { role: 'user', content: text }]);
    setDraft('');
    setActivity('thinking');
    if (context && ASSEMBLY.test(text)) startTour(context.legs.length);
    try {
      const answer = await api.jarbasChat(text, conversationId, context);
      loadedConversation.current = answer.conversation_id;
      setConversationId(answer.conversation_id);
      setMessages((current) => [...current, { role: 'assistant', content: answer.reply, provider: answer.provider, model: answer.model }]);
      setLive((current) => (current ? { ...current, usage: { ...current.usage, questions: answer.usage.questions, daily_limit: answer.usage.daily_limit } } : current));
      if (audio && canSpeak()) {
        setActivity('speaking');
        stopSpeech.current = speak(answer.reply, { onEnd: () => setActivity('idle') }, { voiceName: live?.voice?.voice_name, rate: live?.voice?.voice_rate });
      } else {
        setActivity('idle');
      }
    } catch (error) {
      stopTour();
      notice((error as ApiError).message);
      setActivity('idle');
    }
  };

  const toggleMic = () => {
    if (activity === 'listening') {
      recognition.current?.stop();
      return;
    }
    if (!secureContext()) {
      notice('O microfone só funciona em conexão segura (HTTPS). Use o campo de texto.');
      return;
    }
    unlockSpeech();
    interrupt();
    recognition.current = listen({
      onPartial: setDraft,
      onFinal: (text) => void ask(text),
      onError: notice,
      onEnd: () => setActivity((current) => (current === 'listening' ? 'idle' : current)),
    });
    if (recognition.current) setActivity('listening');
  };

  const newConversation = () => {
    interrupt();
    stopTour();
    loadedConversation.current = null;
    setConversationId(null);
    setMessages([]);
    setView('chat');
  };

  const openConversation = (id: string) => {
    loadedConversation.current = null;
    setMessages([]);
    setConversationId(id);
    setView('chat');
  };

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="fixed z-40 right-4 flex items-center gap-2 bg-ink text-paper border border-ink px-3 py-2 shadow-lg"
        style={{ bottom: 'max(1rem, env(safe-area-inset-bottom))' }}
        aria-label="Abrir o Jarbas IA"
      >
        <JarbasAvatar active={false} />
        <span className="font-display font-semibold">Jarbas IA</span>
      </button>
    );
  }

  const providerText = !online
    ? 'Sem conexão: o Jarbas precisa de internet'
    : status.loading && !live
      ? 'Verificando...'
      : available
        ? `Disponível · ${live!.providers.map((p) => p.label).join(', ')}`
        : 'Nenhum provedor de IA configurado no servidor';

  return (
    <section
      role="dialog"
      aria-label="Jarbas IA"
      className="fixed z-40 inset-x-0 bottom-0 md:inset-x-auto md:right-4 md:bottom-4 md:w-[420px] bg-paper border border-ink shadow-2xl flex flex-col max-h-[88vh] md:max-h-[680px]"
      style={{ paddingBottom: 'env(safe-area-inset-bottom)' }}
    >
      <header className="flex items-center gap-1 px-3 py-2 border-b border-ink">
        <JarbasAvatar active={online && available} activity={activity} />
        <div className="min-w-0 flex-1 ml-1">
          <p className="font-display font-black leading-tight">Jarbas IA</p>
          <p className="font-display text-xs text-ink-2 truncate" role="status">
            <span className={cn('inline-block w-2 h-2 rounded-full mr-1', online && available ? 'bg-[#2f6b3a]' : 'bg-rule')} />
            {activity !== 'idle' ? ACTIVITY_LABEL[activity] : providerText}
          </p>
        </div>
        <button className="p-2" onClick={newConversation} aria-label="Nova conversa">
          <Plus size={18} />
        </button>
        <button className="p-2" onClick={() => setView(view === 'history' ? 'chat' : 'history')} aria-label="Histórico de conversas" aria-pressed={view === 'history'}>
          <History size={18} />
        </button>
        <button className="p-2" onClick={() => setView(view === 'settings' ? 'chat' : 'settings')} aria-label="Configurações do Jarbas" aria-pressed={view === 'settings'}>
          <Settings size={18} />
        </button>
        {canSpeak() && (
          <button className="p-2" onClick={() => (audio ? (interrupt(), setAudio(false)) : setAudio(true))} aria-label={audio ? 'Desativar áudio' : 'Ativar áudio'} aria-pressed={audio}>
            {audio ? <Volume2 size={18} /> : <VolumeX size={18} />}
          </button>
        )}
        <button className="p-2" onClick={() => (interrupt(), setOpen(false))} aria-label="Fechar o Jarbas">
          <X size={18} />
        </button>
      </header>

      {view === 'history' && <HistoryView current={conversationId} onOpen={openConversation} onDeleted={(id) => id === conversationId && newConversation()} />}
      {view === 'settings' && <SettingsView onSaved={() => status.reload()} />}

      {view === 'chat' && (
        <>
          <p className="px-3 py-1.5 font-display text-xs border-b border-rule flex flex-wrap justify-between gap-x-2">
            <span>
              {context ? (
                <>
                  Falando sobre: <strong>{context.structure_name}</strong> · {context.symbol}
                </>
              ) : (
                'Sem estrutura na tela: posso consultar mercado, travas e carteira.'
              )}
            </span>
            {usage && (
              <span className="text-ink-2" title="Perguntas hoje e limite diário configurado">
                {usage.questions}/{usage.daily_limit} hoje
              </span>
            )}
          </p>

          <div ref={list} className="flex-1 overflow-y-auto px-3 py-2 space-y-2 min-h-[140px]" aria-live="polite">
            {messages.length === 0 && (
              <p className="np-note">
                Pergunte por texto ou pelo microfone. Eu uso os dados reais do app, digo quando um dado não existe e não envio ordens.
              </p>
            )}
            {messages.map((message, index) => (
              <div key={index} className={cn('max-w-[92%]', message.role === 'user' ? 'ml-auto text-right' : '')}>
                <p
                  className={cn(
                    'inline-block text-left px-2.5 py-1.5 text-base whitespace-pre-wrap',
                    message.role === 'user' && 'bg-ink text-paper',
                    message.role === 'assistant' && 'border border-rule',
                    message.role === 'notice' && 'text-accent border-l-2 border-accent',
                  )}
                >
                  {message.content}
                </p>
                {message.provider && (
                  <p className="font-display text-[10px] text-ink-2 mt-0.5">
                    via {message.provider}
                    {message.model && ` · ${message.model}`}
                  </p>
                )}
              </div>
            ))}
            {busy && <p className="np-note">{ACTIVITY_LABEL.thinking}</p>}
          </div>

          <div className="px-3 pt-2 flex gap-1.5 overflow-x-auto" aria-label="Sugestões">
            {(context ? SUGGESTIONS_WITH_STRUCTURE : SUGGESTIONS_GENERAL).map((suggestion) => (
              <button key={suggestion} className="np-btn !text-xs whitespace-nowrap" disabled={!ready} onClick={() => void ask(suggestion)}>
                {suggestion}
              </button>
            ))}
          </div>

          {!secureContext() && (
            <p className="px-3 pt-2 font-display text-xs text-accent">Conexão sem HTTPS: microfone indisponível. Use o texto.</p>
          )}

          <form onSubmit={(event: FormEvent) => (event.preventDefault(), void ask(draft))} className="flex items-center gap-2 p-3">
            {canListen() && (
              <button
                type="button"
                onClick={toggleMic}
                disabled={!ready && activity !== 'listening'}
                className={cn('p-3 border rounded-full', activity === 'listening' ? 'bg-accent text-paper border-accent' : 'border-ink')}
                aria-label={activity === 'listening' ? 'Parar de ouvir' : 'Falar com o Jarbas'}
                aria-pressed={activity === 'listening'}
              >
                {activity === 'listening' ? <MicOff size={20} /> : <Mic size={20} />}
              </button>
            )}
            <input
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder={activity === 'listening' ? 'Ouvindo...' : 'Pergunte ao Jarbas'}
              aria-label="Pergunta para o Jarbas"
              maxLength={2000}
              className="np-input flex-1 min-w-0"
            />
            {activity === 'speaking' ? (
              <button type="button" onClick={interrupt} className="p-2 border border-ink" aria-label="Interromper a fala">
                <Square size={18} />
              </button>
            ) : (
              <button type="submit" disabled={!ready || !draft.trim()} className="p-2 border border-ink disabled:opacity-40" aria-label="Enviar">
                <Send size={18} />
              </button>
            )}
          </form>
        </>
      )}
    </section>
  );
}

function HistoryView({ current, onOpen, onDeleted }: { current: string | null; onOpen: (id: string) => void; onDeleted: (id: string) => void }) {
  const conversations = useResource('jarbas-conversations', api.jarbasConversations);
  const remove = async (id: string) => {
    await api.deleteJarbasConversation(id);
    onDeleted(id);
    conversations.reload();
  };
  const items = conversations.data?.conversations ?? [];
  return (
    <div className="flex-1 overflow-y-auto px-3 py-2">
      <h3 className="text-lg mb-2">Conversas anteriores</h3>
      {conversations.loading && !conversations.data && <p className="np-note">Carregando...</p>}
      {conversations.error && <p className="text-accent">{conversations.error.message}</p>}
      {conversations.data && items.length === 0 && <p className="np-note">Nenhuma conversa guardada.</p>}
      <ul>
        {items.map((item) => (
          <li key={item.id} className="np-rule flex items-center gap-2">
            <button className="flex-1 text-left py-2 min-w-0" onClick={() => onOpen(item.id)} aria-current={item.id === current}>
              <span className="block font-display font-semibold text-sm truncate">{item.title}</span>
              <span className="block font-display text-xs text-ink-2">
                {formatMoment(item.updated_at)} · {String(item.messages)} mensagens
              </span>
            </button>
            <button className="p-2" onClick={() => void remove(item.id)} aria-label={`Apagar conversa ${item.title}`}>
              <Trash2 size={16} />
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

function SettingsView({ onSaved }: { onSaved: () => void }) {
  const settings = useResource('jarbas-settings', api.jarbasSettings);
  const models = useResource('jarbas-models', api.jarbasModels);
  const [form, setForm] = useState<JarbasSettings | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const voices = portugueseVoices();

  useEffect(() => setForm(settings.data), [settings.data]);
  if (!form) return <p className="np-note p-3">Carregando configurações...</p>;

  const set = <K extends keyof JarbasSettings>(key: K, value: JarbasSettings[K]) => setForm({ ...form, [key]: value });
  const configured = form.configured_providers;
  const primary = form.provider_order.find((name) => configured.includes(name)) ?? configured[0];
  const choosePrimary = (name: string) => set('provider_order', [name, ...form.provider_order.filter((item) => item !== name)]);
  const catalog = models.data?.models ?? [];
  const selected = catalog.find((model) => model.id === form.openrouter_model);

  const save = async (event: FormEvent) => {
    event.preventDefault();
    setMessage(null);
    setFailure(null);
    try {
      const { updated_at: _updated, configured_providers: _configured, ...body } = form;
      setForm(await api.saveJarbasSettings(body));
      setMessage('Configurações salvas.');
      models.reload();
      onSaved();
    } catch (error) {
      setFailure((error as ApiError).message);
    }
  };

  return (
    <form onSubmit={save} className="flex-1 overflow-y-auto px-3 py-2 space-y-3">
      <h3 className="text-lg">Inteligência artificial</h3>
      {configured.length === 0 && <p className="text-accent text-base">Nenhuma chave de IA no servidor. Configure OPENROUTER_API_KEY na Vercel.</p>}
      {configured.length > 0 && (
        <label className="np-label block">
          Provedor principal
          <select value={primary} onChange={(event) => choosePrimary(event.target.value)} className="np-input block mt-1 w-full">
            {configured.map((name) => (
              <option key={name} value={name}>
                {PROVIDER_LABEL[name] ?? name}
              </option>
            ))}
          </select>
          <span className="block font-display text-xs text-ink-2 mt-1">Os demais entram como reserva, nesta ordem: {form.provider_order.filter((n) => configured.includes(n)).map((n) => PROVIDER_LABEL[n]).join(' → ')}.</span>
        </label>
      )}
      {models.data?.configured && (
        <>
          <label className="np-label block">
            Modelo do OpenRouter
            <select value={form.openrouter_model ?? ''} onChange={(event) => set('openrouter_model', event.target.value || null)} className="np-input block mt-1 w-full">
              <option value="">Automático (gratuitos, com reserva)</option>
              {catalog.map((model) => (
                <option key={model.id} value={model.id} disabled={!model.free && !form.allow_paid}>
                  {model.free ? 'Grátis · ' : `Pago US$ ${model.prompt_per_million?.toFixed(2)}/${model.completion_per_million?.toFixed(2)} por milhão · `}
                  {model.id}
                </option>
              ))}
            </select>
            <span className="block font-display text-xs text-ink-2 mt-1">
              {catalog.filter((m) => m.free).length} gratuitos e {catalog.filter((m) => !m.free).length} pagos agora. Em uso, nesta ordem:{' '}
              {(models.data.chain ?? []).join(' → ') || '—'}.
            </span>
          </label>
          <label className="flex items-start gap-2 text-base">
            <input type="checkbox" checked={form.allow_paid} onChange={(event) => set('allow_paid', event.target.checked)} className="mt-1" />
            <span>
              Autorizo modelos pagos. <span className="text-accent">Pode gerar cobrança no OpenRouter.</span>
            </span>
          </label>
          {selected && !selected.free && <p className="text-accent text-base">Modelo pago selecionado: cada pergunta gera custo.</p>}
        </>
      )}
      <div className="flex flex-wrap gap-3">
        <label className="np-label">
          Perguntas por dia
          <input type="number" min={1} max={2000} value={form.daily_limit} onChange={(event) => set('daily_limit', Number(event.target.value))} className="np-input block mt-1 w-28" />
        </label>
        <label className="np-label">
          Guardar conversas (dias)
          <input type="number" min={1} max={3650} value={form.retention_days} onChange={(event) => set('retention_days', Number(event.target.value))} className="np-input block mt-1 w-28" />
        </label>
      </div>

      <h3 className="text-lg pt-2">Voz</h3>
      {!canSpeak() && <p className="np-note">Este navegador não fala. As respostas aparecem só em texto.</p>}
      <label className="flex items-center gap-2 text-base">
        <input type="checkbox" checked={form.speak_replies} onChange={(event) => set('speak_replies', event.target.checked)} />
        Ler as respostas em voz alta
      </label>
      {voices.length > 0 && (
        <label className="np-label block">
          Voz
          <select value={form.voice_name ?? ''} onChange={(event) => set('voice_name', event.target.value || null)} className="np-input block mt-1 w-full">
            <option value="">Automática (masculina, quando houver)</option>
            {voices.map((voice) => (
              <option key={voice.name} value={voice.name}>
                {voice.name} ({voice.lang})
              </option>
            ))}
          </select>
        </label>
      )}
      <label className="np-label block">
        Velocidade da fala: {form.voice_rate.toFixed(1)}x
        <input type="range" min={0.5} max={2} step={0.1} value={form.voice_rate} onChange={(event) => set('voice_rate', Number(event.target.value))} className="block w-full mt-1 accent-ink" />
      </label>
      <p className="font-display text-xs text-ink-2">
        Reconhecimento de voz: {canListen() ? 'disponível neste navegador' : 'indisponível neste navegador (use o texto)'}
        {secureContext() ? '' : ' · exige HTTPS'}.
      </p>

      <div className="flex items-center gap-3 pb-2">
        <button type="submit" className="np-btn" aria-label="Salvar configurações do Jarbas">
          Salvar
        </button>
        {message && <span role="status">{message}</span>}
      </div>
      {failure && <p role="alert" className="text-accent text-base">{failure}</p>}
    </form>
  );
}
