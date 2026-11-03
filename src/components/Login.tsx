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
    <div className="min-h-screen p-4 md:p-8 max-w-[1400px] mx-auto">
      <h1 className="text-[clamp(3rem,10vw,7.5rem)] leading-[0.95] tracking-tight border-b-4 border-ink pb-3">B3 Opções Pro</h1>
      <form onSubmit={submit} className="max-w-sm mt-8 space-y-4">
        {!ready && (
          <p role="alert" className="text-accent">
            O login ainda não foi configurado no servidor.
          </p>
        )}
        <label className="block np-label">
          Senha
          <input
            type="password"
            autoComplete="current-password"
            autoFocus
            required
            disabled={!ready}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className="np-input mt-1 w-full disabled:opacity-50"
          />
        </label>
        {error && (
          <p role="alert" className="text-accent">
            {error}
          </p>
        )}
        <button type="submit" disabled={!ready || sending || !password} className="np-btn w-full">
          {sending ? 'Entrando...' : 'Entrar'}
        </button>
      </form>
    </div>
  );
}
