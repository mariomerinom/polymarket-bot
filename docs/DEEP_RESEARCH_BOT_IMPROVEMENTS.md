# Deep Research: Mejoras Profesionales para el Bot de Polymarket

> **Fecha:** 2026-03-29
> **Metodo:** 5 agentes de investigacion en paralelo, 100+ fuentes consultadas
> **Objetivo:** Identificar mejoras de alto impacto respaldadas por evidencia academica y profesional

---

## Resumen Ejecutivo

El bot actual tiene una base solida (67% WR, $0 costo, momentum validado). Las mejoras mas impactantes son:

1. **Order flow imbalance** - el feature con mayor alfa no utilizado (Sharpe 3.19 vs 1.44)
2. **Maker orders en Polymarket** - elimina ~1.8% de fee drag y gana rebates
3. **Kelly Criterion fraccional** - sizing matematicamente optimo para 67% WR
4. **Funding rate + Open Interest** - gratis via Coinalyze, confirma/desmiente momentum
5. **ADX + RSI divergence** - filtros profesionales de tendencia y agotamiento

---

## Tabla de Impacto

| # | Mejora | Impacto | Dificultad | Datos disponibles | Validacion |
|---|--------|---------|------------|-------------------|------------|
| 1 | Order flow imbalance | CRITICO | Media | Binance API (gratis) | Academica (t-stat=29.33) |
| 2 | Maker orders en Polymarket | ALTO | Alta | Polymarket CLOB API | Documentado |
| 3 | Kelly Criterion fraccional | ALTO | Baja | Ya tenemos WR | Matematica |
| 4 | Funding rate + OI | ALTO | Baja | Coinalyze (gratis) | Academica + comunidad |
| 5 | ADX trend strength filter | ALTO | Baja | Calculable de candles | Arxiv paper |
| 6 | CVD (Cumulative Volume Delta) | ALTO | Media | Coinalyze/Binance | Academica |
| 7 | RSI divergence | MEDIO | Baja | Calculable de candles | Estandar profesional |
| 8 | Multi-timeframe filtering | MEDIO | Media | Kraken (ya usado) | QuantPedia (7yr backtest) |
| 9 | CUSUM strategy degradation | MEDIO | Baja | Datos internos | Academica |
| 10 | Hurst exponent regime | MEDIO | Media | Calculable de candles | Academica |
| 11 | VWAP anclado | MEDIO | Media | Calculable de candles | Profesional |
| 12 | Weekend conviction boost | BAJO | Baja | Ya existe feature | Peer-reviewed |
| 13 | Cyclical time encoding | BAJO | Baja | Trivial | Estandar ML |
| 14 | Sentiment (Fear & Greed) | BAJO | Baja | alternative.me (gratis) | Academica (daily) |

---

## 1. ORDER FLOW IMBALANCE (Prioridad #1)

### Que es
La proporcion de volumen comprador vs vendedor en cada vela. El bot actualmente usa volumen total pero NO distingue compra de venta.

### Por que es critico
Un paper de EFMA 2025 encontro que order flow imbalance tiene:
- **Sharpe 3.19-3.63** vs 1.44-2.68 para momentum/indicadores tecnicos solos
- Un incremento de 1 desviacion estandar en order flow = +1.9% retorno diario (t-stat=29.33)
- Relacion casi lineal con cambios de precio a corto plazo

### Como obtener los datos (GRATIS)

**Opcion A - Binance Futures API (recomendada):**
```
GET /futures/data/takerlongshortRatio
```
Devuelve taker buy/sell volume pre-calculado por intervalo. No requiere auth.

**Opcion B - Kraken/Coinbase WebSocket:**
Cada trade incluye un campo `side` (taker direction). Acumular por lado en cada intervalo.

**Opcion C - Coinalyze API (mas facil):**
```
GET /v1/cumulative-volume-delta?symbols=BTCUSD
```
CVD pre-calculado, 40 calls/min gratis.

### Implementacion sugerida
```python
# Pseudo-delta desde Binance (gratis, sin websocket)
taker_ratio = taker_buy_volume / (taker_buy_volume + taker_sell_volume)
order_flow_imbalance = taker_ratio - 0.5  # centered at 0

# Interpretar con posicion relativa al VWAP (de la estrategia Delta+VWAP)
if order_flow_imbalance > 0 and price > vwap:
    # Compras retail arriba de VWAP = posible reversion (absorcion)
elif order_flow_imbalance > 0 and price < vwap:
    # Compras institucionales abajo de VWAP = entrada
```

### Fuentes
- EFMA 2025: Order Flow and Cryptocurrency Returns
- Binance API Docs: Taker Buy/Sell Volume
- Coinalyze API Documentation

---

## 2. MAKER ORDERS EN POLYMARKET

### El problema actual
El bot calcula si apostar, pero cuando vaya a live trading, entrar como **taker** en Polymarket cuesta:

| Precio de entrada | Fee efectivo |
|-------------------|-------------|
| ~50% (mid-market) | ~1.80% |
| ~70% / ~30% | ~1.20% |
| ~90% / ~10% | ~0.20% |

Con 67% WR y odds cercanas a even-money, el fee de 1.8% se come una parte significativa del edge.

### La solucion
**Usar maker orders (limit orders):**
- Fee: **0%** (cero)
- Ademas ganas **rebates diarios** en USDC (20% de taker fees recolectados en crypto markets)
- El bot deberia colocar limit orders unos centavos mejor que el mercado y esperar fill

### Arquitectura para live trading
```
1. Bot detecta senal de momentum
2. En vez de market buy, coloca limit order en el bid+1 cent
3. Espera fill (timeout 30-60 seg)
4. Si no fill, ajustar o cancelar
5. Tracking de fills parciales
```

### Consideraciones
- Requiere integracion con Polymarket CLOB API (mas complejo que la Gamma API actual)
- Riesgo de no-fill si el mercado se mueve rapido
- Latencia: necesitas VPS cerca de la infraestructura de Polymarket (<150ms)

### Fuentes
- Polymarket CLOB Documentation
- Polymarket Fees Documentation
- Finance Magnates: Dynamic Fees Analysis

---

## 3. KELLY CRITERION FRACCIONAL

### Formula para prediction markets
```
f* = (b * p - q) / b

donde:
  p = probabilidad real estimada (ej: 0.67 para 67% WR)
  q = 1 - p = 0.33
  b = (1 - market_price) / market_price  (net odds)
```

### Ejemplo con el bot (67% WR, mercado al 50%)
```
b = 0.50 / 0.50 = 1.0
f* = (1.0 * 0.67 - 0.33) / 1.0 = 0.34 (Full Kelly = 34% del bankroll)

Half Kelly = 17%
Quarter Kelly = 8.5%
```

### Sizing recomendado por conviccion

| Conviccion | Kelly Fraction | % del bankroll | Con bankroll $10K |
|-----------|---------------|----------------|-------------------|
| 0-2 (skip) | 0x | 0% | $0 |
| 3 (standard) | 0.25x Kelly | ~3-5% | $300-500 |
| 4 (high) | 0.40x Kelly | ~5-8% | $500-800 |
| 5 (maximum) | 0.50x Kelly | ~8-10% | $800-1,000 |

### Limites duros (no negociables)
```python
MAX_SINGLE_BET = 0.05 * current_bankroll    # 5% hard cap
MIN_BET = 5.00                                # Minimo significativo
MAX_DAILY_LOSS = 0.04 * current_bankroll     # 4% daily stop
MAX_OPEN_EXPOSURE = 0.30 * current_bankroll  # 30% total desplegado
```

### Fee-adjusted Kelly
```python
adjusted_edge = (estimated_prob - market_price) - fee_rate
f_adjusted = adjusted_edge / odds
# Siempre restar fees del edge ANTES de calcular Kelly
```

### Fuentes
- Stanford Kelly Criterion
- arXiv: Kelly Criterion in Prediction Markets (2412.14144)
- Wikipedia: Kelly Criterion

---

## 4. FUNDING RATE + OPEN INTEREST

### Que son
- **Funding rate:** Tasa que pagan longs a shorts (o viceversa) cada 8h en futuros perpetuos. Mide desequilibrio de posicionamiento.
- **Open Interest (OI):** Total de contratos de futuros abiertos. Mide cuanta "carga" tiene el mercado.

### Senales concretas

| Funding | OI Change | Precio | Interpretacion |
|---------|-----------|--------|----------------|
| Positivo alto (>0.10%/8h) | Subiendo | Subiendo | Momentum confirmado pero cargando resorte |
| Positivo extremo (>0.15%/8h) | Subiendo | Subiendo | PELIGRO - cascada de liquidaciones inminente |
| Negativo | Subiendo | Bajando | Shorts acumulando - posible squeeze |
| Cualquiera | Cayendo | Cayendo | Desapalancamiento, capitulacion (posible rebote) |

### Feature compuesto: "Leverage Heat"
```python
leverage_heat = funding_rate * oi_change_rate_1h
# Cuando spike: reducir conviccion en bets de momentum (crowd overleveraged)
```

### API gratuita: Coinalyze
```
GET /v1/funding-rate?symbols=BTCUSD.6         # Funding actual
GET /v1/open-interest?symbols=BTCUSD.6         # OI actual
GET /v1/funding-rate-predicted?symbols=BTCUSD.6 # Funding predicho
```
40 calls/min gratis. Sin auth.

### Fuentes
- Gate.io: Derivatives Market Signals 2025
- Amberdata: Oct 2025 Crash Analysis ($19B OI eliminated in 36h)
- Coinalyze API Documentation

---

## 5. ADX TREND STRENGTH FILTER

### Que es
Average Directional Index - mide la FUERZA de una tendencia sin importar la direccion. Rango 0-100.

### Parametros optimos para crypto (arxiv validated)
- **Periodo:** 10-13 (no el default de 14)
- **Umbral de trade:** ADX > 20 = tendencia suficiente para operar
- **Combo optimo:** ADX(13) + MACD(17,21,15) supero estrategias basadas en EMA

### Implementacion
```python
def adx_filter(candles, period=10, threshold=20):
    """Solo operar cuando ADX > threshold (tendencia fuerte)."""
    # Calcular True Range, +DI, -DI, ADX
    adx = calculate_adx(candles, period)
    return adx > threshold
```

### Impacto esperado
Filtra el "chop" lateral que genera falsos positivos en el detector de rachas. El bot actualmente NO tiene filtro de fuerza de tendencia - solo detecta regimen (trending/mean-reverting) via autocorrelacion.

### Fuentes
- arxiv 2511.00665: Technical Analysis Meets Machine Learning (MACD+ADX optimal params)
- ChartGuys: ADX Indicator Guide
- BingX: ADX for Crypto Trading

---

## 6. CVD (CUMULATIVE VOLUME DELTA)

### Que es
Suma acumulada de (volumen_compra - volumen_venta) a traves del tiempo. Muestra la presion neta.

### Senales clave para el bot

| CVD | Precio | Interpretacion |
|-----|--------|----------------|
| Subiendo | Subiendo | Momentum genuino (confirmar trade) |
| Bajando | Subiendo | **DIVERGENCIA** - momentum falso, reversion inminente |
| Subiendo | Bajando | Acumulacion oculta, posible rebote |
| Bajando | Bajando | Tendencia bajista confirmada |

### Implementacion multi-timeframe
- CVD 4H/diario para bias general
- CVD 1H para puntos de entrada
- Divergencia CVD-precio como senal de agotamiento (complementa compression/volume spike actual)

### Fuentes
- Phemex Academy: CVD Indicator
- Bookmap: CVD Knowledge Base
- LuxAlgo: CVD Explained
- PipPenguin: CVD Trading Guide 2026

---

## 7. RSI DIVERGENCE

### Que es
Cuando el precio hace nuevos maximos pero el RSI hace maximos mas bajos (o viceversa). Senal clasica de agotamiento.

### Por que agregarlo
El bot detecta agotamiento con compression + volume spike + shrinking range. RSI divergence es una senal independiente que captura un aspecto diferente del agotamiento (debilitamiento del momentum interno).

### Parametros
- RSI periodo 5-7 para 5-min candles (no el default de 14)
- Overbought: 80 (no 70) para filtrar ruido
- Oversold: 20 (no 30)

### Implementacion
```python
def rsi_divergence(candles, period=7):
    """Detectar divergencia precio-RSI."""
    rsi = calculate_rsi(candles, period)
    price_highs = [c['high'] for c in candles[-5:]]
    rsi_highs = rsi[-5:]

    # Bearish divergence: precio sube, RSI baja
    if price_highs[-1] > price_highs[-3] and rsi_highs[-1] < rsi_highs[-3]:
        return "bearish_divergence"
    # Bullish divergence: precio baja, RSI sube
    if price_highs[-1] < price_highs[-3] and rsi_highs[-1] > rsi_highs[-3]:
        return "bullish_divergence"
    return None
```

### Fuentes
- Multiple trading education sources
- BitcoinMagazinePro: Divergence Trading
- eplanetbrokers.com: RSI Settings for 5-Minute Charts

---

## 8. MULTI-TIMEFRAME FILTERING

### Evidencia
QuantPedia (backtest 7 anos, Dec 2018 - Nov 2025):

| Config | Sharpe | Max Drawdown |
|--------|--------|-------------|
| Single timeframe MACD | 0.33 | -23.9% |
| D1 filter + H1 entry | 0.80 | -12.4% |
| D1 filter + H1 + candle stop | 1.07 | -7% |

### Implementacion para el bot
```
1H candles → determinar bias (tendencia general)
15m candles → detectar rachas + agotamiento (senal actual)

Si 1H y 15m coinciden → conviction +1
Si 1H y 15m no coinciden → skip o conviction -1
```

El bot YA busca candles de 5m y 15m. Agregar 1H es trivial (`fetch_btc_candles(interval="60m")`).

### Fuentes
- QuantPedia: Multi-Timeframe Trend Strategy on Bitcoin

---

## 9. CUSUM PARA DETECTAR DEGRADACION DE ESTRATEGIA

### Que es
Algoritmo que acumula desviaciones del rendimiento esperado. Probado como **el metodo mas rapido** para detectar cambios en tasa de error fija (Moustakides, 1986).

### Formula
```python
S_t = max(0, S_{t-1} + (expected_win_rate - actual_outcome) - drift)
# Cuando S_t > threshold → ALARMA: estrategia degradandose
```

### Parametros recomendados
```python
DRIFT = 0.02          # Tolerancia para varianza normal
THRESHOLD = 4.5       # Desviaciones estandar del P&L por trade
DETECTION_SPEED = ~40  # Observaciones para detectar transicion
```

### Complemento: Rolling metrics
| Metrica | Ventana | Alarma | Accion |
|---------|---------|--------|--------|
| Win rate | 50 trades | < 50% | Reducir a 1/4 de size |
| Win rate | 100 trades | < 55% | PAUSAR estrategia |
| Max perdidas consecutivas | Running | > 8 | Mitad de size |
| Drawdown desde pico | Running | > 20% | Pausar nuevos trades |

### Fuentes
- StrategyQuant: CUSUM Implementation
- QuantStart: HMM Regime Detection
- Northinfo: CUSUM for Portfolios

---

## 10. HURST EXPONENT (Mejor Regimen Detector)

### Que es
H > 0.5 = trending (momentum funciona)
H < 0.5 = mean-reverting
H = 0.5 = random walk

### Por que es mejor que autocorrelacion
- La autocorrelacion del bot usa solo lag-1. El Hurst exponent captura persistencia a multiples escalas.
- Bitcoin a resolucion de 10 segundos muestra H > 0.7 consistentemente (fuertemente trending en micro-timescales).
- El cambio en Hurst a traves del tiempo senala cambios de regimen.

### Implementacion
```python
def hurst_exponent(prices, window=50):
    """Rolling Hurst exponent via R/S analysis."""
    # R/S (Rescaled Range) method
    returns = np.diff(np.log(prices))
    n = len(returns)
    mean_r = np.mean(returns)

    # Cumulative deviation from mean
    Y = np.cumsum(returns - mean_r)
    R = max(Y) - min(Y)  # Range
    S = np.std(returns)   # Standard deviation

    RS = R / S if S > 0 else 0
    H = np.log(RS) / np.log(n) if RS > 0 and n > 1 else 0.5
    return H
```

### Fuentes
- Macrosynergy Research: Hurst Exponent for Trends
- MDPI: Hurst Exponent in Crypto Pairs
- Samara Asset Management: Hurst for Fund Managers

---

## 11. HALLAZGOS SOBRE POLYMARKET ESPECIFICAMENTE

### Latency arbitrage esta MUERTO (2026)
- Un bot convirtio $313 en $414K-$515K con 98-99% WR usando latency arb
- Polymarket lo mato con fees dinamicas + remocion del delay de 500ms
- Ventana de arbitraje comprimida de 12.3s a 2.7s; el 73% del arb restante lo capturan bots sub-100ms

### 15-minute > 5-minute para edge
- 5-min BTC binary options: pricing MUY eficiente, edge razor-thin
- 15-min: mas tiempo para momentum, pricing menos eficiente, mejor edge
- **Esto valida la expansion del bot a 15m**

### Timing optimo de entrada
- **US market open (9:30 AM ET):** Volatilidad de stocks derrama a crypto
- **Announcements (Fed, CPI):** Senales direccionales mas fuertes
- **Low-liquidity (3-6 AM ET):** Spreads mas amplios, menos bots, mas mispricing
- **Ultimos 15-30 seg de ventana:** Maximo info pero riesgo de latencia blockchain

### Fees por precio de entrada
```
50% odds → ~1.80% fee (PEOR)
70%/30%  → ~1.20%
90%/10%  → ~0.20% (MEJOR)
```
**Implicacion:** Preferir entradas en odds extremas donde fees son menores.

---

## 12. HALLAZGOS ACADEMICOS CLAVE

### Paper: Volume-Weighted Time Series Momentum (SSRN 2024)
- Sharpe 2.17 con momentum ponderado por volumen
- **Accion:** Usar volume ratio como peso de la senal, no solo como flag binario de agotamiento

### Paper: Cryptocurrency Risk-Managed Momentum (ScienceDirect 2025)
- Momentum funciona en crypto pero sufre crashes severos
- **Accion:** Volatility management es critico. Escalar posicion inversamente a volatilidad.

### Paper: Weekend Effect in Crypto Momentum (ACR 2025)
- Retornos de momentum significativamente mayores en fines de semana
- Sharpe mas alto, max drawdown mas bajo los weekends
- **Accion:** Weekend conviction boost (feature existe en V3 pero no se usa)

### Paper: Bitcoin Intraday Momentum (U. Reading)
- Momentum intraday funciona MEJOR en mercados bajistas
- **Accion:** Reconsiderar el filtro DOWN+NEUTRAL que bloquea bets bajistas - puede estar dejando dinero en la mesa

### Paper: Turn-of-Candle Anomaly (PMC 2023)
- Retornos positivos concentrados en minutos 0, 15, 30, 45 de cada hora
- **Accion:** Alinear ciclos del bot a estos boundaries

---

## 13. QUE NO FUNCIONA (Ahorra tiempo)

| Idea | Veredicto | Por que |
|------|-----------|---------|
| LSTMs para 5-15m | NO | XGBoost los supera con features ingenierizados (54.9% vs 53.6%) |
| Transformers para 5-15m | NO | 50.1% accuracy - basicamente coin flip |
| Sentiment en tiempo real | NO para 5-15m | Opera en escala horaria/diaria, no minutos |
| On-chain data | NO para 5-15m | Latencia inherente de horas, no minutos |
| Latency arbitrage | MUERTO | Polymarket lo mato con fees dinamicas en 2026 |
| Full Kelly sizing | PELIGROSO | Drawdowns extremos; usar 0.25x-0.50x |

---

## Plan de Implementacion Sugerido

### Fase 1: Quick Wins (1-2 dias, sin datos externos nuevos)
- [ ] Kelly Criterion fraccional para sizing
- [ ] ADX filter (calculable de candles existentes)
- [ ] RSI divergence como senal de agotamiento adicional
- [ ] CUSUM para monitoreo de degradacion
- [ ] Weekend conviction boost (feature ya existe)
- [ ] Cyclical time encoding (sin/cos de hora)

### Fase 2: Datos Externos Gratuitos (3-5 dias)
- [ ] Coinalyze API: funding rate + OI + CVD
- [ ] Binance API: taker buy/sell volume (order flow)
- [ ] Multi-timeframe: agregar candles de 1H como filtro
- [ ] Fear & Greed Index como regimen diario

### Fase 3: Infraestructura para Live Trading (1-2 semanas)
- [ ] Integracion con Polymarket CLOB API (maker orders)
- [ ] VPS cerca de infraestructura Polymarket
- [ ] Sistema de execution con limit orders + timeout
- [ ] Kelly-based dynamic bankroll management

### Fase 4: Refinamiento (ongoing)
- [ ] Hurst exponent como reemplazo de autocorrelacion
- [ ] VWAP anclado como filtro de regimen
- [ ] Ratio de absorcion (delta/cambio-precio)
- [ ] Backtesting de cada mejora con 50+ bets antes de produccion

---

## Fuentes Completas

### Papers Academicos
- EFMA 2025: Order Flow and Cryptocurrency Returns
- SSRN 4825389: Volume-Weighted Time Series Momentum (Sharpe 2.17)
- ScienceDirect 2025: Cryptocurrency Risk-Managed Momentum
- ACR Journal 2025: Weekend Effect in Crypto Momentum
- ScienceDirect 2022: Intraday Return Predictability
- U. Reading: Bitcoin Intraday Time-Series Momentum
- PMC 2023: Turn-of-the-Candle Effect in Bitcoin
- SSRN 5209907: Catching Crypto Trends (Sharpe > 1.5)
- Wiley 2020: HMM Regime Detection in Crypto
- arxiv 2511.00665: Technical Analysis + ML (MACD+ADX params)
- arxiv 2412.14144: Kelly Criterion in Prediction Markets
- MDPI: Hurst Exponent in Crypto

### APIs y Herramientas
- Coinalyze API (gratis): CVD, OI, funding rate
- Binance Futures API (gratis): Taker buy/sell volume
- CoinGlass: Aggregated CVD + volume footprint
- Freqtrade: Open-source bot con orderflow
- Polymarket CLOB API: Maker orders

### Guias y Analisis
- QuantPedia: Multi-Timeframe BTC Strategy (7yr backtest)
- Polymarket Official Docs: CLOB, Fees, Market Making
- Finance Magnates: Dynamic Fees Analysis
- PolyTrack: 15-Minute Crypto Guide
- Stanford: Kelly Criterion
- Bookmap: Absorption & Exhaustion Patterns

---

*Documento generado: 2026-03-29*
*5 agentes de investigacion, 100+ fuentes, analisis cruzado*
