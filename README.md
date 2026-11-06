# Baleias

Monitor só de leitura de carteiras grandes da Hyperliquid. Não tem chave e não envia ordem. As regras estão em `PROTOCOLO.md`.

- Ver resultado: `python3 -m baleias relatorio`
- Backtest (otimista, nunca libera dinheiro): `python3 -m baleias backtest`
- Serviços: `systemctl --user status baleias baleias-painel`
- Painel: http://127.0.0.1:8787 (só nesta máquina; de outro computador: `ssh -L 8787:127.0.0.1:8787 usuario@servidor`)
- Alertas: `dados/alertas.log`. Telegram: criar `~/baleias/.env` com `TELEGRAM_BOT_TOKEN=` e `TELEGRAM_CHAT_ID=`, depois `systemctl --user restart baleias`.

O aprendizado: cada sinal é gravado com a previsão antes de o resultado existir. Depois de 4 h, o resultado é calculado com custos, classificado (acerto, custo comeu o ganho, entrada tardia, devolveu o ganho, carteira saiu antes, contra desde o início), ajusta os pesos do modelo em `dados/baleias.db` e pode gerar lições candidatas ou aposentar uma carteira.

## Robô da Binance
- Começa **simulado**: preços reais da Binance, sem ordens. Resultado no painel e em `journalctl --user -u baleias-robo`.
- Regra (desde 2026-11-06, a pedido do dono): compra US$ 10 quando o modelo de 15 min prevê alta; vende em 15 min ou no stop de 0,5% (`ROBO_STOP_PCT`). Stop diário de US$ 2 (`ROBO_PERDA_DIA`).
- Parar na hora: `touch ~/baleias/PARAR` (apagar o arquivo para voltar).
- Dinheiro real (decisão do dono): criar uma chave de API na Binance **só com "Enable Spot & Margin Trading"**, **sem saque**, travada no IP desta máquina, e pôr no `~/baleias/.env`:
  `BINANCE_API_KEY=...`, `BINANCE_API_SECRET=...`, `BINANCE_REAL=1`; depois `systemctl --user restart baleias-robo`. O robô recusa chave que permita saque. Precisa de pelo menos 10 USDT livres na conta spot.
