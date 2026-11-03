import { Bot, Loader2 } from 'lucide-react';
import { FormEvent, useState } from 'react';
import { api, ApiError } from '../services/api';

export function Login({ ready, onSuccess }: { ready: boolean; onSuccess: () => void }) {
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setSending(true);
    setError(null);
    try {
      await api.login(password);
      onSuccess();
    } catch (failure) {
      setError((failure as ApiError).message);
      setPassword('');
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-slate-950">
      <form onSubmit={submit} className="w-full max-w-sm bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-4">
        <div className="flex items-center gap-2 text-sky-400">
          <Bot className="w-6 h-6" />
          <h1 className="font-bold text-lg text-white">B3 Opções Pro</h1>
        </div>
        {!ready && (
          <p role="alert" className="text-sm text-amber-200">
            O login ainda não foi configurado no servidor.
          </p>
        )}
        <label className="block text-sm text-slate-300">
          Senha
          <input
            type="password"
            autoComplete="current-password"
            autoFocus
            required
            disabled={!ready}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className="mt-1 w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white outline-none focus:border-sky-500 disabled:opacity-50"
          />
        </label>
        {error && (
          <p role="alert" className="text-sm text-red-300">
            {error}
          </p>
        )}
        <button
          type="submit"
          disabled={!ready || sending || !password}
          className="w-full flex justify-center py-2 rounded-lg bg-sky-500 text-slate-950 font-bold hover:bg-sky-400 disabled:opacity-50 transition-colors"
        >
          {sending ? <Loader2 className="w-5 h-5 animate-spin" /> : 'Entrar'}
        </button>
      </form>
    </div>
  );
}
