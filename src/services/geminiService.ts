/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { GoogleGenAI, Type } from "@google/genai";
import { AssetData, Strategy, StrategyType, Trend } from "../types";

const ai = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY || "" });

export async function analyzeMarketAndSuggestStrategy(asset: AssetData): Promise<Strategy> {
  const prompt = `
    Você é um especialista em opções da B3 (Bolsa Brasileira). 
    Analise o seguinte ativo:
    Ticker: ${asset.ticker}
    Preço Atual: R$ ${asset.price}
    Tendência: ${asset.trend}
    Volatilidade: ${asset.volatility}%

    Objetivo: Recomendar a melhor estratégia de opções (Bull Call Spread, Bear Put Spread, Iron Condor ou Straddle).
    
    Regras:
    1. Se Tendência = bullish, use Bull Call Spread.
    2. Se Tendência = bearish, use Bear Put Spread.
    3. Se Tendência = neutral e Volatilidade baixa, use Iron Condor.
    4. Se Tendência = neutral e Volatilidade alta, use Straddle.
    
    Calcule strikes realistas (aproximadamente +/- 5% do preço atual).
    Defina vencimento para 30 dias.
    
    Retorne a resposta EXATAMENTE no formato JSON fornecido.
  `;

  try {
    const response = await ai.models.generateContent({
      model: "gemini-3-flash-preview",
      contents: prompt,
      config: {
        responseMimeType: "application/json",
        responseSchema: {
          type: Type.OBJECT,
          properties: {
            type: { type: Type.STRING },
            description: { type: Type.STRING },
            maxProfit: { type: Type.NUMBER },
            maxLoss: { type: Type.NUMBER },
            probability: { type: Type.NUMBER },
            cost: { type: Type.NUMBER },
            stepByStep: {
              type: Type.ARRAY,
              items: { type: Type.STRING }
            },
            legs: {
              type: Type.ARRAY,
              items: {
                type: Type.OBJECT,
                properties: {
                  action: { type: Type.STRING },
                  option: {
                    type: Type.OBJECT,
                    properties: {
                      strike: { type: Type.NUMBER },
                      premium: { type: Type.NUMBER },
                      type: { type: Type.STRING },
                      expiry: { type: Type.STRING },
                      ticker: { type: Type.STRING }
                    }
                  }
                }
              }
            }
          }
        }
      }
    });

    const data = JSON.parse(response.text);
    return {
      ...data,
      id: Math.random().toString(36).substr(2, 9),
      ticker: asset.ticker
    };
  } catch (error) {
    console.error("Erro ao analisar com Gemini:", error);
    // Fallback strategy if AI fails
    return getFallbackStrategy(asset);
  }
}

function getFallbackStrategy(asset: AssetData): Strategy {
  return {
    id: 'fallback',
    type: StrategyType.BULL_CALL_SPREAD,
    ticker: asset.ticker,
    description: 'Estratégia sugerida automaticamente (Modo Fallback)',
    legs: [
      { action: 'BUY', option: { strike: asset.price * 1.02, premium: 1.20, type: 'CALL', expiry: '30d', ticker: asset.ticker + 'C' + (asset.price * 1.02).toFixed(0) } },
      { action: 'SELL', option: { strike: asset.price * 1.05, premium: 0.50, type: 'CALL', expiry: '30d', ticker: asset.ticker + 'C' + (asset.price * 1.05).toFixed(0) } }
    ],
    maxProfit: 1.80,
    maxLoss: 0.70,
    probability: 65,
    cost: 0.70,
    stepByStep: ['Identificar tendência de alta', 'Comprar CALL no strike mais baixo', 'Vender CALL no strike mais alto', 'Aguardar valorização']
  };
}
