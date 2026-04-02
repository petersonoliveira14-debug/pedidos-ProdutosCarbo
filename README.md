# Dashboard de Vendas — Grupo Carbo

[![Sync Bling + Deploy](https://github.com/petersonoliveira14-debug/pedidos-ProdutosCarbo/actions/workflows/deploy.yml/badge.svg)](https://github.com/petersonoliveira14-debug/pedidos-ProdutosCarbo/actions/workflows/deploy.yml)

Dashboard interativo para acompanhamento das vendas de **CarboZé** e **CarboPro**, com sincronização automática via Bling API v3.

**Acesso:** https://petersonoliveira14-debug.github.io/pedidos-ProdutosCarbo/

## Funcionalidades

- KPIs de faturamento, volume e ticket médio por período
- Filtros por status, vendedor e semana
- Painel de metas mensais com projeção de fechamento
- Histórico mensal navegável (‹ / ›)
- Exportação de NFs em CSV (compatível com Excel)
- Ranking de vendedores e clientes
- Gráficos de produto e status

## Sincronização automática

O workflow `Sync Bling + Deploy` executa 3x ao dia (09h, 15h, 21h UTC) e:
1. Busca pedidos do mês corrente via Bling API v3
2. Grava `data/pedidos.json`, `data/meta.json` e snapshot histórico `data/historico/YYYY-MM.json`
3. Commita e faz push; o GitHub Pages reflete em ~1 minuto

Em caso de falha, um e-mail de alerta é disparado automaticamente.

## Secrets necessários (GitHub → Settings → Secrets)

| Secret | Descrição |
|---|---|
| `BLING_CLIENT_ID` | OAuth2 Client ID do app Bling |
| `BLING_CLIENT_SECRET` | OAuth2 Client Secret |
| `BLING_REFRESH_TOKEN` | Refresh token (rotacionado automaticamente) |
| `GH_PAT` | Personal Access Token (repo + secrets) |
| `MAIL_USER` | E-mail Gmail para notificações de falha |
| `MAIL_PASS` | App Password do Gmail (2FA) |
