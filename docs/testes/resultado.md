# Relatório de validação local — 03/11/2026

Ambiente: Linux, Python 3.12.14, Node 24.22.1 para verificação sintática opcional, Playwright 1.62.0 com Chromium do sistema. Teste de navegador usa locale pt-BR e fuso America/Sao_Paulo. Dados de todos os testes são fictícios; suíte de domínio/API e navegador usa bancos temporários separados.

## Unidade e integração HTTP

Comando executado na raiz: `python -m unittest discover -s tests -v`.

**Resultado: 20 testes executados, 20 aprovados, 0 falhas, 0 erros, 0 ignorados, 0 falhas esperadas.** Tempo observado da execução aprovada: 3,288 s; não é benchmark.

| Cenário / nome do teste | Esperado | Obtido / situação |
|---|---|---|
| test_authentication_and_hash | Senha correta valida; errada/injeção não; hash não contém senha | Aprovado |
| test_product_create_update_search | Criar, localizar, editar metadados e preservar saldo | Aprovado |
| test_demo_preserves_partially_configured_catalog | Reiniciar com --demo preserva catálogo parcialmente configurado sem misturar dados fictícios | Aprovado |
| test_duplicate_sku_and_lookup | Bloquear códigos e nomes duplicados | Aprovado |
| test_product_validation | Rejeitar campos vazios, referências inexistentes e valores inválidos | Aprovado |
| test_money_exactness | 0,29 → 29 centavos; 123,45 → 12345 | Aprovado |
| test_entry_exit_and_persistence | 10 − 3 = 7, mesmo após reabrir; eventos com usuário/motivo | Aprovado |
| test_insufficient_balance_rolls_back | Saída 4 de saldo 3 falha sem alteração parcial | Aprovado |
| test_movement_validation | Rejeitar tipo, quantidade, motivo e produto inválidos sem eventos | Aprovado |
| test_maximum_balance | Bloquear saldo acima de 999999999 | Aprovado |
| test_archive_preserves_history_and_reserved_sku | Bloquear arquivo com saldo; preservar eventos/código após zerar | Aprovado |
| test_dashboard_and_low_filter | Saldo × preço exato; igual ao mínimo é alerta | Aprovado |
| test_concurrent_exits_are_atomic | Só uma de duas saídas de 4 sobre saldo 5 vence; saldo final 1 | Aprovado |
| test_initialization_repeatable_and_demo | Demo repetido sem duplicação nem troca de senha; integridade ok | Aprovado |
| test_static_assets_and_security_headers | HTML/JS/CSS 200; CSP e nosniff; sem acesso a arquivo arbitrário | Aprovado |
| test_auth_csrf_logout_and_expiry | Privado sem sessão 401; alteração sem CSRF 403; logout e expiração invalidam | Aprovado |
| test_complete_api_flow | Cadastros, edição, entrada/saída, busca, arquivo e respostas HTTP corretas | Aprovado |
| test_json_errors | JSON inválido ou não objeto retorna 400 | Aprovado |
| test_csv_is_authenticated_and_formula_safe | CSV só autenticado e célula de fórmula prefixada | Aprovado |
| test_login_rate_limit | Após 10 tentativas no minuto, resposta 429 | Aprovado |

Primeira execução sob restrição de sockets: os 13 testes de domínio passaram, mas a inicialização da classe de testes HTTP falhou por `PermissionError` ao criar servidor local. Isso era uma restrição do executor; a suíte completa foi executada novamente com permissão de sockets e passou. Não foi ocultado ou ignorado nenhum teste HTTP.

## Fluxo no navegador

Comando: `CHROMIUM_PATH=/usr/bin/chromium python tests/browser_smoke.py`.

**Resultado: fluxo completo aprovado**, sem exceções JavaScript (`pageerror`).

- Login e carregamento dos indicadores.
- Capturas em 1440 px e 390 px; página móvel sem overflow horizontal global.
- Cadastro de categoria e fornecedor.
- Produto com categoria, fornecedor, preço e mínimo; pesquisa pelo código e edição de preço.
- Entrada de 5; tentativa de saída de 6 exibe erro; saída de 5 aceita.
- Histórico com ambos os eventos e motivos.
- Arquivamento depois de zerar saldo.
- Download do CSV com nome esperado.
- Recarregamento mantém sessão; logout volta ao login.

As duas primeiras tentativas de interface pararam em seletores acessíveis: ícones decorativos entravam no nome do link e opções eram incluídas no nome dos selects. Corrigidos com `aria-hidden` e nomes explícitos, respectivamente; a execução completa seguinte passou. Os testes não foram enfraquecidos para aceitar fluxo quebrado.

Capturas da execução aprovada em `docs/prototipos/`. Não são uma homologação em Safari/Firefox ou uma auditoria completa WCAG. Estados vazios e de carregamento foram implementados, mas não têm avaliação formal de usabilidade.

## Execução, persistência e backup

Servidor iniciado pelo comando do README em loopback, porta 8000. Requisições locais verificaram página inicial 200, login 200 e dashboard 200 com **4 produtos, 94 unidades, R$3.427,00 e 2 alertas** da carga fictícia.

Backup criado pela API SQLite com servidor em execução; as cinco tabelas foram comparadas com a origem, com igualdade de dados. A cópia foi reaberta e apresentou `integrity_check=ok`, 94 unidades e valor total 342700 centavos. O servidor foi encerrado e reiniciado para verificar a persistência e a inicialização repetida. O banco e o backup de desenvolvimento ficam em `data/`, ignorado no Git.

## Outras verificações

- `node --check src/estoquepro/static/app.js`: aprovado.
- `python -m compileall -q src`: aprovado.
- Diagramas Graphviz: quatro fontes renderizadas em SVG com `dot`, sem erro.
- Arquivos do projeto e capturas presentes; banco, backups e caches não aparecem como arquivos versionáveis.

## Não executado / limitações

Sem teste de carga, auditoria de segurança independente, validação em Windows/macOS, outros navegadores, teste de leitores de tela, revisão de PDF oficial, revisão no template acadêmico ou apresentação ao professor. Não se declara produção, conformidade oficial da A3 ou entrega remota. Nenhum defeito crítico conhecido foi identificado nos fluxos executados.
