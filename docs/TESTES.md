# Testes e validações

A suíte automatizada (`tests/test_fintrack.py`) testa:

- Cadastro, sessão, senha e controle de acesso.
- Tentativas de login, proteção CSRF e logout.
- Criação, atualização, exclusão e consulta de transações.
- Integridade da categoria conforme o tipo (receita/despesa).
- Isolamento entre duas contas do mesmo usuário e entre usuários diferentes.
- Orçamentos mensais e gastos calculados por categoria.
- Metas, contribuições virtuais e independência do saldo de lançamentos.
- Recorrências, pausa/ativação, idempotência e preservação do dia original de vencimento.
- Importação CSV, validação e prevenção de duplicatas.
- Exportação CSV e neutralização de fórmulas potencialmente perigosas.
- Filtros de relatório e intervalos inválidos.
- Normalização de moeda pt-BR/en-US.

Comando: `python -m pytest -q`.

O script `scripts/smoke_ui.py` valida seis fluxos de interface usando Playwright em HTML real e ponte com FastAPI TestClient: criação/listagem de transação, criação de orçamento, criação e contribuição de meta e alternância de tema. O script é **opcional** e requer Chromium.

O script `scripts/render_previews.py` gera imagens do frontend real com respostas reais da API (capturadas previamente com TestClient) porque o Chromium do ambiente utilizado bloqueou navegação HTTP, inclusive `localhost`. Não são capturas de uma implantação pública.
