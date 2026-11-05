# Baleias

Monitor só de leitura de carteiras grandes da Hyperliquid. Não tem chave e não envia ordem. As regras estão em `PROTOCOLO.md`.

- Ver resultado: `python3 -m baleias relatorio`
- Backtest (otimista, nunca libera dinheiro): `python3 -m baleias backtest`
- Serviços: `systemctl --user status baleias baleias-painel`
- Painel: http://127.0.0.1:8787 (só nesta máquina; de outro computador: `ssh -L 8787:127.0.0.1:8787 usuario@servidor`)
- Alertas: `dados/alertas.log`. Telegram: criar `~/baleias/.env` com `TELEGRAM_BOT_TOKEN=` e `TELEGRAM_CHAT_ID=`, depois `systemctl --user restart baleias`.

O aprendizado: cada sinal é gravado com a previsão antes de o resultado existir. Depois de 4 h, o resultado é calculado com custos, classificado (acerto, custo comeu o ganho, entrada tardia, devolveu o ganho, carteira saiu antes, contra desde o início), ajusta os pesos do modelo em `dados/baleias.db` e pode gerar lições candidatas ou aposentar uma carteira.
