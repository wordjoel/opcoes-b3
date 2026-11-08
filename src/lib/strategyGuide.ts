/** Explicação didática de cada estrutura, em linguagem simples. Não é recomendação. */

export type MarketView = 'ALTA' | 'BAIXA' | 'LATERAL' | 'MOVIMENTO';

export const VIEW_LABEL: Record<MarketView, string> = {
  ALTA: 'Alta',
  BAIXA: 'Baixa',
  LATERAL: 'Lateral',
  MOVIMENTO: 'Movimento forte',
};

export const VIEW_QUESTION: Record<MarketView, string> = {
  ALTA: 'Acho que vai subir',
  BAIXA: 'Acho que vai cair',
  LATERAL: 'Acho que vai ficar parado',
  MOVIMENTO: 'Vai mexer muito, não sei para onde',
};

export interface StrategyGuide {
  view: MarketView;
  level: 'Iniciante' | 'Intermediário';
  whatIs: string;
  wins: string;
  loses: string;
  careful: string;
}

export const GUIDES: Record<string, StrategyGuide> = {
  long_call: {
    view: 'ALTA',
    level: 'Iniciante',
    whatIs: 'Você paga um prêmio pelo direito de comprar o ativo pelo preço de exercício (strike) até o vencimento.',
    wins: 'Quando o ativo sobe acima do strike mais o prêmio pago. Quanto mais sobe, mais ganha.',
    loses: 'Se o ativo terminar abaixo do strike, a opção vira pó e você perde o prêmio inteiro, nada além disso.',
    careful: 'O tempo corre contra: a cada dia sem alta, a opção perde valor (theta).',
  },
  long_put: {
    view: 'BAIXA',
    level: 'Iniciante',
    whatIs: 'Você paga um prêmio pelo direito de vender o ativo pelo strike até o vencimento. Funciona como um seguro contra queda.',
    wins: 'Quando o ativo cai abaixo do strike menos o prêmio pago.',
    loses: 'Se o ativo terminar acima do strike, você perde o prêmio inteiro, nada além disso.',
    careful: 'Precisa de queda antes do vencimento; parado, perde valor a cada dia.',
  },
  bull_call_spread: {
    view: 'ALTA',
    level: 'Iniciante',
    whatIs: 'Trava de alta: compra uma call e vende outra call de strike mais alto. A venda barateia a compra, em troca de um teto para o ganho.',
    wins: 'Com o ativo acima do strike vendido no vencimento: ganha a distância entre os strikes menos o que pagou.',
    loses: 'Com o ativo abaixo do strike comprado: perde só o débito pago na montagem.',
    careful: 'Ganho e perda são limitados e conhecidos desde o início. Monte as duas pernas juntas.',
  },
  bear_put_spread: {
    view: 'BAIXA',
    level: 'Iniciante',
    whatIs: 'Trava de baixa: compra uma put e vende outra put de strike mais baixo, para pagar menos pela proteção.',
    wins: 'Com o ativo abaixo do strike vendido no vencimento: ganha a distância entre os strikes menos o que pagou.',
    loses: 'Com o ativo acima do strike comprado: perde só o débito pago.',
    careful: 'Ganho e perda limitados. Se cair além do strike vendido, o ganho não aumenta.',
  },
  bull_put_spread: {
    view: 'ALTA',
    level: 'Intermediário',
    whatIs: 'Trava de alta com crédito: vende uma put abaixo do preço atual e compra outra mais abaixo como proteção. Você recebe dinheiro na montagem.',
    wins: 'Se o ativo ficar acima da put vendida: as duas viram pó e o crédito fica com você. Serve até com o ativo parado.',
    loses: 'Se cair abaixo da put comprada: perde a distância entre os strikes menos o crédito recebido.',
    careful: 'A perna vendida pede margem na corretora. Se for americana, pode ser exercida antes do vencimento.',
  },
  bear_call_spread: {
    view: 'BAIXA',
    level: 'Intermediário',
    whatIs: 'Trava de baixa com crédito: vende uma call acima do preço atual e compra outra mais acima como proteção. Você recebe dinheiro na montagem.',
    wins: 'Se o ativo ficar abaixo da call vendida: o crédito fica com você. Serve até com o ativo parado.',
    loses: 'Se subir acima da call comprada: perde a distância entre os strikes menos o crédito.',
    careful: 'A perna vendida pede margem. Se for americana, pode ser exercida antes, perto de dividendos.',
  },
  long_straddle: {
    view: 'MOVIMENTO',
    level: 'Intermediário',
    whatIs: 'Compra uma call e uma put no mesmo strike. Você aposta no tamanho do movimento, não na direção.',
    wins: 'Quando o ativo se afasta muito do strike, para cima ou para baixo, mais do que o total pago.',
    loses: 'Se o ativo ficar parado perto do strike: perde as duas opções, que é a perda máxima.',
    careful: 'É caro e perde valor rápido. Faz mais sentido com vol implícita barata e um evento à frente.',
  },
  long_strangle: {
    view: 'MOVIMENTO',
    level: 'Intermediário',
    whatIs: 'Compra uma call acima e uma put abaixo do preço atual. Mais barato que o straddle.',
    wins: 'Com um movimento forte que passe de uma das pontas mais o custo total.',
    loses: 'Se o ativo terminar entre os dois strikes, perde tudo o que pagou.',
    careful: 'Exige um movimento ainda maior que o straddle para dar lucro.',
  },
  iron_condor: {
    view: 'LATERAL',
    level: 'Intermediário',
    whatIs: 'Junta duas travas de crédito: uma de alta com puts e uma de baixa com calls. Monta uma faixa onde você ganha.',
    wins: 'Se o ativo terminar entre a put vendida e a call vendida: fica com o crédito inteiro.',
    loses: 'Se sair da faixa além de uma das proteções: perde a largura da trava menos o crédito.',
    careful: 'Quatro pernas, quatro custos de corretagem. Pede margem e atenção perto do vencimento.',
  },
  iron_butterfly: {
    view: 'LATERAL',
    level: 'Intermediário',
    whatIs: 'Vende call e put no mesmo strike central e compra proteções dos dois lados. Crédito maior que o do condor.',
    wins: 'O máximo acontece com o ativo exatamente no strike central no vencimento.',
    loses: 'Se o ativo se afastar além de uma das proteções: perde a largura menos o crédito.',
    careful: 'A faixa de lucro é estreita. Pede margem nas pernas vendidas.',
  },
  call_butterfly: {
    view: 'LATERAL',
    level: 'Intermediário',
    whatIs: 'Compra uma call abaixo, vende duas no centro e compra uma acima. Custa pouco e aposta num preço-alvo.',
    wins: 'O máximo acontece com o ativo no strike central no vencimento.',
    loses: 'Longe do centro, para qualquer lado, perde só o pequeno débito pago.',
    careful: 'É difícil acertar o centro; o lucro grande depende de o ativo parar perto dele.',
  },
  call_calendar: {
    view: 'LATERAL',
    level: 'Intermediário',
    whatIs: 'Trava calendário (ou horizontal): vende uma call do vencimento curto e compra uma call do mesmo strike no vencimento longo. A curta perde valor mais rápido que a longa.',
    wins: 'Se o ativo estiver perto do strike no vencimento curto: a vendida vira pó e a comprada ainda vale bastante. Você pode vendê-la ou vender outra curta (rolar).',
    loses: 'Se o ativo se afastar muito do strike, para cima ou para baixo: as duas ficam parecidas e você perde até o débito pago.',
    careful: 'O ganho é estimado: depende da vol da perna longa naquele dia. Vol subindo ajuda; vol caindo atrapalha. Feche ou role a curta antes de vencer.',
  },
  put_calendar: {
    view: 'LATERAL',
    level: 'Intermediário',
    whatIs: 'Trava calendário com puts: vende a put do vencimento curto e compra a put do mesmo strike no vencimento longo.',
    wins: 'Com o ativo parado perto do strike no vencimento curto, como na calendário com call.',
    loses: 'Com movimento grande para qualquer lado: perde até o débito pago.',
    careful: 'Put americana vendida dentro do dinheiro pode ser exercida antes. Ganho máximo é estimativa do modelo.',
  },
  call_diagonal: {
    view: 'ALTA',
    level: 'Intermediário',
    whatIs: 'Trava diagonal: compra uma call do vencimento longo perto do preço atual e vende uma call do vencimento curto com strike mais alto. Mistura trava de alta e calendário.',
    wins: 'Com alta lenta até perto do strike vendido no vencimento curto: a vendida vira pó e a comprada ganhou valor.',
    loses: 'Com queda forte, ou alta muito rápida e muito além do strike vendido: perde até o débito.',
    careful: 'Depois do vencimento curto você pode vender outra call curta e repetir. Ganho máximo é estimativa.',
  },
  put_diagonal: {
    view: 'BAIXA',
    level: 'Intermediário',
    whatIs: 'Diagonal de baixa: compra uma put do vencimento longo perto do preço atual e vende uma put do vencimento curto com strike mais baixo.',
    wins: 'Com queda lenta até perto do strike vendido no vencimento curto.',
    loses: 'Com alta forte, ou queda muito rápida além do strike vendido: perde até o débito.',
    careful: 'A put vendida, se americana, pode ser exercida antes. Ganho máximo é estimativa do modelo.',
  },
};

/** Guia da estrutura: as travas da varredura usam o guia do seu tipo. */
export function guideOf(item: { key: string; family?: string }): StrategyGuide | undefined {
  return GUIDES[item.family ?? item.key] ?? GUIDES[item.key.split('#')[0]];
}

export interface AssemblyLeg {
  symbol: string;
  action: 'BUY' | 'SELL';
  kind: 'CALL' | 'PUT';
  strike: number;
  quantity: number;
  premium: number;
  /** Só em estruturas com dois vencimentos. */
  expiry?: string;
}

export interface AssemblyStep {
  leg: AssemblyLeg;
  /** Positivo: você paga. Negativo: você recebe. */
  cash: number;
  role: string;
}

/**
 * Ordem prática de montagem: primeiro as compras, depois as vendas, para nunca ficar
 * com uma venda descoberta no meio do caminho.
 */
export function assemblySteps(legs: AssemblyLeg[]): AssemblyStep[] {
  const cashOf = (leg: AssemblyLeg) => (leg.action === 'BUY' ? 1 : -1) * leg.premium * leg.quantity;
  const credit = legs.reduce((total, leg) => total + cashOf(leg), 0) < 0;
  return [...legs]
    .sort((a, b) => (a.action === b.action ? 0 : a.action === 'BUY' ? -1 : 1))
    .map((leg) => ({
      leg,
      cash: cashOf(leg),
      role:
        leg.action === 'BUY'
          ? credit
            ? 'Proteção: você paga pelo direito, e é isso que limita a perda da estrutura.'
            : 'Aposta principal: você paga pelo direito de ganhar com o movimento.'
          : credit
            ? 'Fonte do crédito: você recebe o prêmio e assume a obrigação.'
            : leg.expiry && legs.some((other) => other.expiry !== leg.expiry)
              ? 'Perna curta: vence antes e perde valor mais rápido; é ela que paga parte da longa.'
              : 'Financiamento: você recebe um prêmio que barateia a compra, em troca de limitar o ganho.',
    }));
}
