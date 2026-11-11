import { CSSProperties, FormEvent, useEffect, useState } from 'react';
import { api, ApiError, useResource } from '../services/api';
import { DecisionEntry, PortfolioView } from '../types';
import { formatCurrency, formatDay, formatMoment, formatNumber, saoPauloDate } from '../lib/utils';
import { paraCampo, parseNumeroBR } from '../lib/numero';
import { ErrorNotice, Loading, Panel, Signed, Stat } from './Common';

type Section = 'carteira' | 'decisoes';

export function Carteira() {
  const [section, setSection] = useState<Section>('carteira');
  return (
    <div className="space-y-4">
      <header>
        <h2 className="text-4xl md:text-5xl">Carteira</h2>
        <p className="np-note mt-1">
          Operações já feitas na corretora, informadas por você. O app não envia ordens: só usa a carteira para avaliar as estruturas.
        </p>
      </header>
      <nav aria-label="Seções da carteira" className="flex flex-wrap gap-2 border-y border-ink py-2">
        {(
          [
            ['carteira', 'Posições e operações'],
            ['decisoes', 'Registro de decisões'],
          ] as [Section, string][]
        ).map(([id, label]) => (
          <button key={id} aria-current={section === id ? 'page' : undefined} onClick={() => setSection(id)} className="np-btn">
            {label}
          </button>
        ))}
      </nav>
      {section === 'carteira' ? <Positions /> : <Decisions />}
    </div>
  );
}

function Positions() {
  const portfolio = useResource('portfolio', api.portfolio);
  const [view, setView] = useState<PortfolioView | null>(null);
  useEffect(() => setView(portfolio.data), [portfolio.data]);

  if (portfolio.loading && !view) return <Loading label="Lendo a carteira..." />;
  if (portfolio.error) return <ErrorNotice error={portfolio.error} onRetry={portfolio.reload} />;
  if (!view) return null;

  const voidFill = async (id: number) => {
    setView(await api.voidFill(id));
  };

  return (
    <div className="space-y-4">
      <SettingsForm view={view} onSaved={setView} />
      <div className="np-facts np-rule" style={{ '--np-columns': 4 } as CSSProperties}>
        <Stat label="Caixa" value={formatCurrency(view.cash_brl)} hint="Inicial, operações e custos" />
        <Stat label="Resultado realizado" value={<Signed value={view.realized_pnl_brl}>{formatCurrency(view.realized_pnl_brl)}</Signed>} hint="Bruto" />
        <Stat label="Custos informados" value={formatCurrency(view.fees_brl)} />
        <Stat label="Realizado líquido" value={<Signed value={view.realized_net_brl}>{formatCurrency(view.realized_net_brl)}</Signed>} hint="Antes do imposto" />
      </div>
      <FillForm onSaved={setView} />
      <Panel title="Posições abertas" className="overflow-x-auto">
        {view.positions.length === 0 ? (
          <p>Nenhuma posição aberta.</p>
        ) : (
          <table className="np-table min-w-[480px]">
            <thead>
              <tr>
                <th scope="col">Série</th>
                <th scope="col" className="text-right">Quantidade</th>
                <th scope="col" className="text-right">Preço médio</th>
              </tr>
            </thead>
            <tbody>
              {view.positions.map((position) => (
                <tr key={position.symbol}>
                  <td>{position.symbol}</td>
                  <td className="text-right">{formatNumber(position.quantity, 0)}</td>
                  <td className="text-right">{formatCurrency(position.avg_entry_price)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>
      <Panel title="Operações informadas" className="overflow-x-auto">
        {view.fills.length === 0 ? (
          <p>Nenhuma operação informada.</p>
        ) : (
          <table className="np-table min-w-[760px]">
            <thead>
              <tr>
                <th scope="col">Data</th>
                <th scope="col">Série</th>
                <th scope="col">Lado</th>
                <th scope="col" className="text-right">Qtd.</th>
                <th scope="col" className="text-right">Preço</th>
                <th scope="col" className="text-right">Custos</th>
                <th scope="col">Situação</th>
              </tr>
            </thead>
            <tbody>
              {view.fills.map((fill) => (
                <tr key={fill.id} className={fill.voided_at ? 'line-through text-ink-2' : undefined}>
                  <td>{formatDay(fill.trade_day)}</td>
                  <td>{fill.symbol}</td>
                  <td>{fill.side === 'BUY' ? 'Compra' : 'Venda'}</td>
                  <td className="text-right">{formatNumber(fill.quantity, 0)}</td>
                  <td className="text-right">{formatCurrency(fill.price)}</td>
                  <td className="text-right">{formatCurrency(fill.fees_brl)}</td>
                  <td>
                    {fill.voided_at ? (
                      `Anulada em ${formatMoment(fill.voided_at)}`
                    ) : (
                      <button className="np-btn" onClick={() => voidFill(fill.id)} aria-label={`Anular operação ${fill.id}`}>
                        Anular
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>
    </div>
  );
}

function SettingsForm({ view, onSaved }: { view: PortfolioView; onSaved: (view: PortfolioView) => void }) {
  const [cash, setCash] = useState(view.settings ? paraCampo(view.settings.initial_cash_brl) : '');
  const [limit, setLimit] = useState(view.settings ? paraCampo(view.settings.max_position_size) : '');
  const [failure, setFailure] = useState<string | null>(null);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setFailure(null);
    const caixa = parseNumeroBR(cash);
    const maximo = parseNumeroBR(limit);
    if (!caixa.ok || !maximo.ok) {
      setFailure(!caixa.ok ? `Caixa: ${caixa.reason}` : `Máximo por série: ${(maximo as { reason: string }).reason}`);
      return;
    }
    try {
      onSaved(await api.savePortfolioSettings(caixa.value, maximo.value));
    } catch (error) {
      setFailure((error as ApiError).status === 422 ? 'Caixa a partir de zero e limite inteiro positivo.' : (error as ApiError).message);
    }
  };

  return (
    <form onSubmit={submit} className="np-section flex flex-wrap items-end gap-3">
      <div className="basis-full md:basis-auto md:max-w-sm">
        <h3 className="text-xl">Caixa e limite por série</h3>
        <p className="font-display text-xs text-ink-2 mt-1">
          {view.settings
            ? `Última alteração: ${formatMoment(view.settings.updated_at)}`
            : 'Sem esses valores, as estruturas não são conferidas contra a carteira.'}
        </p>
      </div>
      <label className="np-label">
        Caixa inicial (R$)
        <input type="text" inputMode="decimal" required value={cash} onChange={(event) => setCash(event.target.value)} placeholder="ex.: 10.000,00" className="np-input block mt-1 w-40" />
      </label>
      <label className="np-label">
        Máximo por série (opções)
        <input type="text" inputMode="numeric" required value={limit} onChange={(event) => setLimit(event.target.value)} placeholder="ex.: 5" className="np-input block mt-1 w-40" />
      </label>
      <button type="submit" className="np-btn" aria-label="Salvar carteira">
        Salvar
      </button>
      {failure && <p role="alert" className="basis-full text-accent text-base">{failure}</p>}
    </form>
  );
}

function FillForm({ onSaved }: { onSaved: (view: PortfolioView) => void }) {
  const [symbol, setSymbol] = useState('');
  const [side, setSide] = useState<'BUY' | 'SELL'>('BUY');
  const [quantity, setQuantity] = useState('');
  const [price, setPrice] = useState('');
  const [fees, setFees] = useState('');
  const [day, setDay] = useState(saoPauloDate());
  const [failure, setFailure] = useState<string | null>(null);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setFailure(null);
    const qtd = parseNumeroBR(quantity);
    const preco = parseNumeroBR(price);
    const custo = fees.trim() === '' ? { ok: true as const, value: 0 } : parseNumeroBR(fees);
    if (!qtd.ok || !preco.ok || !custo.ok) {
      const motivo = !qtd.ok ? `Quantidade: ${qtd.reason}` : !preco.ok ? `Preço: ${preco.reason}` : `Custos: ${(custo as { reason: string }).reason}`;
      setFailure(motivo);
      return;
    }
    try {
      onSaved(await api.addFill({ symbol, side, quantity: qtd.value, price: preco.value, fees_brl: custo.value, trade_day: day }));
      setSymbol('');
      setQuantity('');
      setPrice('');
      setFees('');
    } catch (error) {
      setFailure((error as ApiError).message);
    }
  };

  return (
    <form onSubmit={submit} className="np-section flex flex-wrap items-end gap-3">
      <h3 className="text-xl basis-full">Informar operação feita</h3>
      <label className="np-label">
        Série
        <input required maxLength={16} value={symbol} onChange={(event) => setSymbol(event.target.value.toUpperCase())} className="np-input block mt-1 w-32" />
      </label>
      <label className="np-label">
        Lado
        <select value={side} onChange={(event) => setSide(event.target.value as 'BUY' | 'SELL')} className="np-input block mt-1">
          <option value="BUY">Compra</option>
          <option value="SELL">Venda</option>
        </select>
      </label>
      <label className="np-label">
        Quantidade
        <input type="text" inputMode="numeric" required value={quantity} onChange={(event) => setQuantity(event.target.value)} placeholder="ex.: 100" className="np-input block mt-1 w-28" />
      </label>
      <label className="np-label">
        Preço (R$)
        <input type="text" inputMode="decimal" required value={price} onChange={(event) => setPrice(event.target.value)} placeholder="ex.: 0,35" className="np-input block mt-1 w-28" />
      </label>
      <label className="np-label">
        Custos (R$)
        <input type="text" inputMode="decimal" value={fees} onChange={(event) => setFees(event.target.value)} placeholder="ex.: 4,90" className="np-input block mt-1 w-24" />
      </label>
      <label className="np-label">
        Data
        <input type="date" required value={day} max={saoPauloDate()} onChange={(event) => setDay(event.target.value)} className="np-input block mt-1" />
      </label>
      <button type="submit" className="np-btn">
        Registrar
      </button>
      {failure && <p role="alert" className="basis-full text-accent text-base">{failure}</p>}
    </form>
  );
}

const STATUS: Record<string, string> = { APROVADA: 'Aprovada', REPROVADA: 'Reprovada', INCOMPLETA: 'Incompleta' };

function Decisions() {
  const decisions = useResource('decisions', api.decisions);
  const [open, setOpen] = useState<string | null>(null);
  if (decisions.loading && !decisions.data) return <Loading label="Lendo o registro..." />;
  if (decisions.error) return <ErrorNotice error={decisions.error} onRetry={decisions.reload} />;
  const items: DecisionEntry[] = decisions.data?.decisions ?? [];
  return (
    <Panel title="Últimas decisões mostradas" className="overflow-x-auto">
      <p className="np-note mb-2">Cada análise de estrutura fica registrada com os dados que a originaram. A mesma análise repetida não duplica.</p>
      {items.length === 0 ? (
        <p>Nenhuma decisão registrada ainda.</p>
      ) : (
        <table className="np-table min-w-[760px]">
          <thead>
            <tr>
              <th scope="col">Quando</th>
              <th scope="col">Ativo</th>
              <th scope="col">Vencimento</th>
              <th scope="col">Estrutura</th>
              <th scope="col">Decisão</th>
              <th scope="col">Dados</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id}>
                <td>{formatMoment(item.created_at)}</td>
                <td>{item.symbol}</td>
                <td>{formatDay(item.expiry)}</td>
                <td>{item.structure_key}</td>
                <td>
                  {STATUS[item.status] ?? item.status}
                  {[...item.reasons, ...item.missing].length > 0 && (
                    <ul className="text-sm text-ink-2">
                      {[...item.reasons, ...item.missing].map((reason) => (
                        <li key={reason}>{reason}</li>
                      ))}
                    </ul>
                  )}
                </td>
                <td>
                  <button className="np-btn" onClick={() => setOpen(open === item.id ? null : item.id)} aria-expanded={open === item.id}>
                    {open === item.id ? 'Ocultar' : 'Ver'}
                  </button>
                  {open === item.id && <pre className="text-xs whitespace-pre-wrap max-w-md mt-1">{JSON.stringify(item.inputs, null, 2)}</pre>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Panel>
  );
}
