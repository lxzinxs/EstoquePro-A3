# Requisitos e rastreabilidade

Versão inicial implementada a partir do texto do solicitante. Validação contra o PDF oficial pendente. Ator único: administrador de estoque.

## Requisitos funcionais

### RF001 — Autenticar e encerrar sessão

- **Descrição:** o sistema permite autenticar e encerrar sessão.
- **Ator:** Administrador. **Prioridade:** Alta.
- **Entradas:** Usuário e senha / ação Sair.
- **Processamento:** Valida hash e cria ou invalida sessão.
- **Saídas:** Sessão ou mensagem.
- **Regras de negócio:** Sessão absoluta de 8 h; login limitado por IP.
- **Critérios de aceitação:** Login correto abre painel; senha errada recebe 401; sair invalida cookie.
- **Verificação:** `HttpTests.test_auth_csrf_logout_and_expiry`.
- **Rastreio:** UC01 → T01 → `server.py`.

### RF002 — Cadastrar categoria

- **Descrição:** o sistema permite cadastrar categoria.
- **Ator:** Administrador. **Prioridade:** Alta.
- **Entradas:** Nome de 1 a 80 caracteres.
- **Processamento:** Remove espaços e persiste nome único.
- **Saídas:** Identificador e lista atualizada.
- **Regras de negócio:** Não aceitar nome vazio ou duplicado sob NOCASE SQLite.
- **Critérios de aceitação:** Categoria criada pode ser selecionada no produto.
- **Verificação:** `InventoryTests.test_duplicate_sku_and_lookup; browser_smoke.py`.
- **Rastreio:** UC02 → T02 → `domain.py` + `app.js`.

### RF003 — Cadastrar fornecedor

- **Descrição:** o sistema permite cadastrar fornecedor.
- **Ator:** Administrador. **Prioridade:** Média.
- **Entradas:** Nome de 1 a 80 caracteres.
- **Processamento:** Valida e persiste nome único.
- **Saídas:** Identificador e lista atualizada.
- **Regras de negócio:** Vínculo de fornecedor no produto é opcional.
- **Critérios de aceitação:** Fornecedor cadastrado aparece no seletor.
- **Verificação:** `InventoryTests.test_duplicate_sku_and_lookup; HttpTests.test_complete_api_flow`.
- **Rastreio:** UC03 → T03 → `domain.py` + `app.js`.

### RF004 — Cadastrar produto

- **Descrição:** o sistema permite cadastrar produto.
- **Ator:** Administrador. **Prioridade:** Alta.
- **Entradas:** Código, nome, categoria, fornecedor opcional, preço e mínimo.
- **Processamento:** Valida e insere produto ativo com saldo zero.
- **Saídas:** Produto no catálogo.
- **Regras de negócio:** Código único inclusive entre arquivados; categoria obrigatória.
- **Critérios de aceitação:** Produto persiste com saldo zero e preço em centavos.
- **Verificação:** `InventoryTests.test_product_create_update_search; test_product_validation`.
- **Rastreio:** UC04 → T04 → `domain.py` + `app.js`.

### RF005 — Editar produto

- **Descrição:** o sistema permite editar produto.
- **Ator:** Administrador. **Prioridade:** Alta.
- **Entradas:** Id e metadados do produto.
- **Processamento:** Atualiza apenas metadados de produto ativo.
- **Saídas:** Produto atualizado.
- **Regras de negócio:** Não permite editar saldo pela atualização cadastral.
- **Critérios de aceitação:** Preço/nome alteram e saldo anterior permanece.
- **Verificação:** `InventoryTests.test_product_create_update_search`.
- **Rastreio:** UC05 → T05 → `domain.py` + `app.js`.

### RF006 — Consultar e filtrar produtos

- **Descrição:** o sistema permite consultar e filtrar produtos.
- **Ator:** Administrador. **Prioridade:** Alta.
- **Entradas:** Texto, categoria e opção estoque baixo.
- **Processamento:** Consulta ativos e combina filtros na interface.
- **Saídas:** Lista e contagem ou estado vazio.
- **Regras de negócio:** Busca textual por nome/código; baixo inclui saldo igual ao mínimo.
- **Critérios de aceitação:** Pesquisa pelo código encontra o item; termo inexistente não retorna item.
- **Verificação:** `InventoryTests.test_product_create_update_search; test_dashboard_and_low_filter`.
- **Rastreio:** UC06 → T06 → `domain.py` + `app.js`.

### RF007 — Registrar entrada

- **Descrição:** o sistema permite registrar entrada.
- **Ator:** Administrador. **Prioridade:** Alta.
- **Entradas:** Produto, quantidade inteira positiva, motivo.
- **Processamento:** Transação incrementa saldo e grava evento.
- **Saídas:** Id do evento e saldo atualizado.
- **Regras de negócio:** Limite de saldo 999999999; somente produtos ativos.
- **Critérios de aceitação:** Entrada de 10 em saldo zero resulta em saldo 10 e evento.
- **Verificação:** `InventoryTests.test_entry_exit_and_persistence; test_maximum_balance`.
- **Rastreio:** UC07 → T07 → `domain.py` + `app.js`.

### RF008 — Registrar saída

- **Descrição:** o sistema permite registrar saída.
- **Ator:** Administrador. **Prioridade:** Alta.
- **Entradas:** Produto, quantidade inteira positiva, motivo.
- **Processamento:** Transação valida saldo, decrementa e grava evento.
- **Saídas:** Id do evento ou erro sem alteração.
- **Regras de negócio:** Saldo nunca negativo; escritas concorrentes serializadas.
- **Critérios de aceitação:** Saída maior que saldo não altera saldo nem histórico.
- **Verificação:** `InventoryTests.test_insufficient_balance_rolls_back; test_concurrent_exits_are_atomic`.
- **Rastreio:** UC08 → T08 → `domain.py` + `app.js`.

### RF009 — Consultar histórico

- **Descrição:** o sistema permite consultar histórico.
- **Ator:** Administrador. **Prioridade:** Alta.
- **Entradas:** Acesso à página Movimentações.
- **Processamento:** Relaciona eventos com usuário e produto.
- **Saídas:** Até 200 eventos recentes, data, motivo e saldo após.
- **Regras de negócio:** Histórico não é editável ou excluível via API.
- **Critérios de aceitação:** Após entrada e saída, ambos os eventos aparecem em ordem decrescente.
- **Verificação:** `InventoryTests.test_entry_exit_and_persistence; browser_smoke.py`.
- **Rastreio:** UC09 → T09 → `domain.py` + `app.js`.

### RF010 — Arquivar produto

- **Descrição:** o sistema permite arquivar produto.
- **Ator:** Administrador. **Prioridade:** Média.
- **Entradas:** Id de produto e confirmação.
- **Processamento:** Marca produto inativo quando saldo é zero.
- **Saídas:** Produto ausente do catálogo ativo.
- **Regras de negócio:** Mantém código reservado e histórico; sem exclusão física.
- **Critérios de aceitação:** Saldo não zero bloqueia; saldo zero arquiva sem apagar eventos.
- **Verificação:** `InventoryTests.test_archive_preserves_history_and_reserved_sku`.
- **Rastreio:** UC10 → T10 → `domain.py` + `app.js`.

### RF011 — Consultar painel e alertas

- **Descrição:** o sistema permite consultar painel e alertas.
- **Ator:** Administrador. **Prioridade:** Alta.
- **Entradas:** Acesso à Visão geral.
- **Processamento:** Agrega produtos ativos, unidades, valor e baixo estoque.
- **Saídas:** Indicadores, eventos recentes e alertas.
- **Regras de negócio:** Valor é soma de saldo × preço atual; não representa custo fiscal.
- **Critérios de aceitação:** Um produto com 2 un. a R$12,90 resulta em R$25,80.
- **Verificação:** `InventoryTests.test_dashboard_and_low_filter`.
- **Rastreio:** UC11 → T11 → `domain.py` + `app.js`.

### RF012 — Exportar posição de estoque

- **Descrição:** o sistema permite exportar posição de estoque.
- **Ator:** Administrador. **Prioridade:** Média.
- **Entradas:** Ação Baixar CSV.
- **Processamento:** Consulta ativos e serializa CSV UTF-8 BOM com ponto e vírgula.
- **Saídas:** Arquivo estoquepro.csv.
- **Regras de negócio:** Exige sessão; neutraliza fórmulas; inclui todo estoque ativo.
- **Critérios de aceitação:** Arquivo contém cabeçalho e produtos ativos; sem sessão retorna 401.
- **Verificação:** `HttpTests.test_csv_is_authenticated_and_formula_safe; browser_smoke.py`.
- **Rastreio:** UC12 → T12 → `server.py`.

## Requisitos não funcionais

| ID | Categoria e requisito verificável | Evidência / limite |
|---|---|---|
| RNF001 | **Segurança:** Hash PBKDF2-SHA256 com 260000 iterações e salt aleatório; nunca guardar senha em texto. | test_authentication_and_hash; inspeção de hash. |
| RNF002 | **Segurança de sessão:** Alterações sem CSRF retornam 403 e consultas privadas sem sessão retornam 401. | test_auth_csrf_logout_and_expiry. |
| RNF003 | **Integridade:** Impedir saldo negativo e gravar saldo/evento atomicamente sob duas saídas concorrentes. | test_concurrent_exits_are_atomic; test_insufficient_balance_rolls_back. |
| RNF004 | **Confiabilidade:** Dados permanecem ao reabrir banco; inicialização repetida não duplica demonstração. | test_entry_exit_and_persistence; test_initialization_repeatable_and_demo. |
| RNF005 | **Usabilidade:** Mensagens claras de saldo insuficiente e formulários obrigatórios; estados vazios/carregamento. | browser_smoke.py exercita erro e sucesso; inspeção de estados na interface. |
| RNF006 | **Acessibilidade:** Campos com rótulos, navegação identificada, diálogo nativo, mensagens com role alert/status, sem overflow da página a 390 px. | browser_smoke.py e inspeção; auditoria WCAG completa não realizada. |
| RNF007 | **Compatibilidade:** Rodar a aplicação em Python 3.12+ sem dependências externas obrigatórias; interface em Chromium moderno. | Execução validada neste Linux/Python 3.12 e Chromium; Windows e outros navegadores não executados. |
| RNF008 | **Manutenibilidade:** Separar interface, HTTP e domínio; disponibilizar suíte unittest reproduzível. | Estrutura src/ e testes executados. |
| RNF009 | **Backup/recuperação:** Backup SQLite consistente deve restaurar contagem e saldos equivalentes com integrity_check=ok. | Verificação operacional registrada em docs/testes/resultado.md. |
| RNF010 | **Desempenho delimitado:** API limita corpo JSON a 16 KB e histórico a 200 eventos; consultas locais de smoke test têm timeout de 5 s. | test_json_errors e fluxo HTTP; sem benchmark de carga ou SLA de produção. |
| RNF011 | **Disponibilidade local:** Após iniciar e autenticar, dashboard responde 200 e pode ser usado sem serviço de banco externo. | Teste funcional e reinicialização; sem promessa de alta disponibilidade. |
| RNF012 | **Exportação segura:** CSV deve prefixar células que possam ser interpretadas como fórmulas. | test_csv_is_authenticated_and_formula_safe. |

## Regras transversais

RB01: quantidades inteiras, positivas nas movimentações e não negativas em mínimos/saldos. RB02: motivo obrigatório (1–240 caracteres). RB03: preço não negativo, até duas casas e no máximo R$99.999.999. RB04: nome de produto de 1–120 caracteres e código de 1–32. RB05: referências de categoria e fornecedor precisam existir. RB06: somente arquivar com saldo zero. RB07: correções são novos eventos compensatórios. RB08: dados de demonstração são fictícios; não usar dados pessoais reais.

## Critério de conclusão acadêmica

Requisitos acima representam o MVP implementado, não comprovam aderência a requisitos desconhecidos do PDF. A entrega final exige revisão da equipe, template oficial e confirmação das exigências do professor. Rastreio local: 15966a9 (domínio), 3101165 (API/interface) e 0754e1c (testes); detalhes por tarefa no backlog. Não houve publicação remota.


## RF013 — Cadastrar usuário local

- **Descrição:** permitir a criação de conta pela aba Cadastro da tela de acesso.
- **Ator:** novo usuário do negócio. **Prioridade:** Alta.
- **Entradas:** usuário de 3–32 caracteres ASCII permitidos, senha de 8–256 caracteres e confirmação.
- **Processamento:** normalizar usuário para minúsculas, validar unicidade sem distinção de caixa, comparar confirmação, criar hash PBKDF2, persistir e abrir sessão.
- **Saídas:** painel autenticado ou mensagem de erro sem conta parcial.
- **Regras:** cadastro disponível somente no servidor vinculado a loopback; contas compartilham estoque e permissões. Não permite recriar usuário existente ou redefinir sua senha pelo cadastro. Mesma proteção de origem, JSON e limite de tentativas do login.
- **Aceitação:** nova conta entra automaticamente; pode sair e entrar novamente; nomes repetidos e senhas divergentes são recusados.
- **Verificação:** `test_register_validation_and_duplicate`, `test_register_login_and_shared_inventory`, `test_register_rejects_invalid_data_and_cross_site` e `browser_smoke.py`.
- **Rastreio:** UC13 → T21 → `Inventory.register`, `/api/register` e formulários de acesso.

### Complemento RF001 — compatibilidade do acesso demo

No início local com `--demo`, a antiga senha padrão é migrada para `admin123` sem perda de dados. Senha personalizada só é redefinida com `--reset-demo-admin`, opção explícita local. Verificado por `test_legacy_demo_migration_preserves_data` e `test_demo_preserves_custom_password_until_explicit_reset`; T22.
