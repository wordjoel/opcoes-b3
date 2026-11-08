/**
 * Voz do Jarbas com recursos nativos do navegador, sem API paga:
 * reconhecimento (Web Speech API) e síntese (speechSynthesis).
 * O suporte varia: Chrome no Android e no desktop reconhecem fala; Safari no iPhone
 * reconhece a partir do iOS 14.5, mas pode não reconhecer no app instalado (PWA).
 * Tudo é detectado em tempo de execução, e a tela só mostra o que existe.
 */

type RecognitionCtor = new () => SpeechRecognitionLike;

interface SpeechRecognitionLike {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  maxAlternatives: number;
  onresult: ((event: { results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal: boolean }> }) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}

function recognitionCtor(): RecognitionCtor | null {
  if (typeof window === 'undefined') return null;
  const w = window as unknown as { SpeechRecognition?: RecognitionCtor; webkitSpeechRecognition?: RecognitionCtor };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

export const canListen = () => recognitionCtor() !== null;
export const canSpeak = () => typeof window !== 'undefined' && 'speechSynthesis' in window && 'SpeechSynthesisUtterance' in window;

const RECOGNITION_ERRORS: Record<string, string> = {
  'not-allowed': 'Permissão do microfone negada. Libere nas configurações do navegador.',
  'service-not-allowed': 'O navegador não liberou o reconhecimento de voz neste modo. Use o campo de texto.',
  'no-speech': 'Não ouvi nada. Tente de novo, mais perto do microfone.',
  'audio-capture': 'Nenhum microfone encontrado.',
  network: 'O reconhecimento de voz precisa de internet.',
  aborted: '',
};

export interface Listening {
  stop(): void;
}

/** Ouve uma frase em português e devolve o texto final. */
export function listen(handlers: {
  onPartial?: (text: string) => void;
  onFinal: (text: string) => void;
  onError: (message: string) => void;
  onEnd: () => void;
}): Listening | null {
  const Ctor = recognitionCtor();
  if (!Ctor) return null;
  const recognition = new Ctor();
  recognition.lang = 'pt-BR';
  recognition.interimResults = true;
  recognition.continuous = false;
  recognition.maxAlternatives = 1;
  let finalText = '';
  recognition.onresult = (event) => {
    let partial = '';
    for (let index = 0; index < event.results.length; index += 1) {
      const result = event.results[index];
      if (result.isFinal) finalText += result[0].transcript;
      else partial += result[0].transcript;
    }
    handlers.onPartial?.((finalText + partial).trim());
  };
  recognition.onerror = (event) => {
    const message = RECOGNITION_ERRORS[event.error] ?? 'Falha no reconhecimento de voz.';
    if (message) handlers.onError(message);
  };
  recognition.onend = () => {
    if (finalText.trim()) handlers.onFinal(finalText.trim());
    handlers.onEnd();
  };
  try {
    recognition.start();
  } catch {
    handlers.onError('Não foi possível iniciar o microfone.');
    return null;
  }
  return { stop: () => recognition.stop() };
}

// Vozes masculinas conhecidas em pt-BR, por sistema. A lista de vozes muda por aparelho.
const MALE_HINTS = ['daniel', 'felipe', 'ricardo', 'antonio', 'antônio', 'fabio', 'fábio', 'humberto', 'donato', 'julio', 'júlio', 'nicolau', 'male', 'masculin'];
const FEMALE_HINTS = ['luciana', 'francisca', 'maria', 'vitoria', 'vitória', 'female', 'feminin', 'joana', 'fernanda', 'helena'];

/** Escolhe uma voz masculina em português, se houver; senão qualquer voz pt-BR com tom mais grave. */
export function pickVoice(voices: SpeechSynthesisVoice[]): { voice: SpeechSynthesisVoice | null; male: boolean } {
  const portuguese = voices.filter((voice) => voice.lang.toLowerCase().replace('_', '-').startsWith('pt'));
  const brazil = portuguese.filter((voice) => voice.lang.toLowerCase().replace('_', '-') === 'pt-br');
  const pool = brazil.length ? brazil : portuguese;
  const named = (voice: SpeechSynthesisVoice, hints: string[]) => hints.some((hint) => voice.name.toLowerCase().includes(hint));
  const male = pool.find((voice) => named(voice, MALE_HINTS));
  if (male) return { voice: male, male: true };
  const neutral = pool.find((voice) => !named(voice, FEMALE_HINTS));
  return { voice: neutral ?? pool[0] ?? null, male: false };
}

/** Texto para leitura: sem marcação nem símbolos que a voz leria em voz alta. */
export function speakable(text: string): string {
  return text
    .replace(/^\s*\|?[\s:|-]{3,}\|?\s*$/gm, '')
    .replace(/^-{3,}$/gm, '')
    .replace(/\|/g, ', ')
    .replace(/[*_#`>]/g, '')
    .replace(/(\d)\.(\d{3})/g, '$1$2')
    .replace(/-?R\$\s?([\d,]+)/g, '$1 reais')
    .replace(/\s+/g, ' ')
    .trim();
}

/** Fala o texto em partes (o Chrome corta falas longas). Devolve uma função que interrompe. */
export function speak(
  text: string,
  handlers: { onStart?: () => void; onEnd?: () => void } = {},
  options: { voiceName?: string | null; rate?: number } = {},
): () => void {
  if (!canSpeak()) {
    handlers.onEnd?.();
    return () => {};
  }
  const synth = window.speechSynthesis;
  synth.cancel();
  const voices = synth.getVoices();
  const chosen = options.voiceName ? voices.find((item) => item.name === options.voiceName) : undefined;
  const { voice, male } = chosen ? { voice: chosen, male: true } : pickVoice(voices);
  const chunks = speakable(text).match(/[^.!?;:]+[.!?;:]*/g) ?? [];
  let cancelled = false;
  chunks.forEach((chunk, index) => {
    const utterance = new SpeechSynthesisUtterance(chunk.trim());
    utterance.lang = voice?.lang ?? 'pt-BR';
    if (voice) utterance.voice = voice;
    utterance.rate = options.rate ?? 1.02;
    // Sem voz masculina instalada, um tom mais grave aproxima o pedido.
    utterance.pitch = male ? 1 : 0.8;
    if (index === 0) utterance.onstart = () => handlers.onStart?.();
    if (index === chunks.length - 1) utterance.onend = () => !cancelled && handlers.onEnd?.();
    synth.speak(utterance);
  });
  if (chunks.length === 0) handlers.onEnd?.();
  return () => {
    cancelled = true;
    synth.cancel();
    handlers.onEnd?.();
  };
}

/** No iPhone, a fala só é liberada depois de um toque: chamar dentro do clique. */
export function unlockSpeech() {
  if (!canSpeak()) return;
  const utterance = new SpeechSynthesisUtterance('');
  utterance.volume = 0;
  window.speechSynthesis.speak(utterance);
}

/** Vozes em português disponíveis neste aparelho, para a escolha nas configurações. */
export function portugueseVoices(): SpeechSynthesisVoice[] {
  if (!canSpeak()) return [];
  return window.speechSynthesis.getVoices().filter((voice) => voice.lang.toLowerCase().startsWith('pt'));
}

/** Microfone e voz exigem HTTPS fora do localhost. */
export const secureContext = () => typeof window === 'undefined' || window.isSecureContext !== false;
