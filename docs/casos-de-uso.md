# Casos de uso

Ator principal de UC01–UC12: **Usuário de estoque** (mesmas permissões do administrador). UC13 tem como ator o novo usuário. Referência visual: `diagramas/casos-de-uso.puml`.

## UC01 — Autenticar e sair

- **Objetivo:** Acesso ao sistema.
- **Ator principal:** Administrador de estoque.
- **Pré-condições:** Aplicação iniciada.
- **Fluxo principal:** Informar usuário e senha; validar credenciais; abrir painel; solicitar Sair; invalidar sessão.
- **Fluxos alternativos:** Sessão já válida abre o painel sem novo login.
- **Exceções:** Senha incorreta: 401; dez tentativas/minuto: 429; sessão expirada exige login.
- **Pós-condições:** Sessão ativa após login ou inválida após logout.
- **Requisito:** RF001.

## UC02 — Cadastrar categoria

- **Objetivo:** Classificar produtos.
- **Ator principal:** Administrador de estoque.
- **Pré-condições:** Sessão ativa.
- **Fluxo principal:** Abrir Categorias; Nova categoria; informar nome; salvar; visualizar cartão.
- **Fluxos alternativos:** Cancelar encerra diálogo sem gravar.
- **Exceções:** Nome vazio: validação; duplicado: 409.
- **Pós-condições:** Categoria persistida e disponível para produtos.
- **Requisito:** RF002.

## UC03 — Cadastrar fornecedor

- **Objetivo:** Registrar parceiro de abastecimento.
- **Ator principal:** Administrador de estoque.
- **Pré-condições:** Sessão ativa.
- **Fluxo principal:** Abrir Fornecedores; Novo fornecedor; informar nome; salvar.
- **Fluxos alternativos:** Produto pode ser criado sem fornecedor.
- **Exceções:** Nome inválido: 400; duplicado: 409.
- **Pós-condições:** Fornecedor persistido.
- **Requisito:** RF003.

## UC04 — Cadastrar produto

- **Objetivo:** Incluir item no catálogo.
- **Ator principal:** Administrador de estoque.
- **Pré-condições:** Sessão ativa e categoria existente.
- **Fluxo principal:** Abrir Produtos; Novo produto; preencher campos; selecionar categoria; salvar.
- **Fluxos alternativos:** Fornecedor pode permanecer sem seleção; cancelar não grava.
- **Exceções:** Código duplicado: 409; categoria inexistente ou preço inválido: 400.
- **Pós-condições:** Produto ativo com saldo zero.
- **Requisito:** RF004.

## UC05 — Editar produto

- **Objetivo:** Atualizar metadados.
- **Ator principal:** Administrador de estoque.
- **Pré-condições:** Sessão ativa e produto ativo.
- **Fluxo principal:** Selecionar Editar; modificar metadados; salvar; consultar item.
- **Fluxos alternativos:** Cancelar preserva metadados anteriores.
- **Exceções:** Produto inexistente/inativo ou campo inválido: 400; código já usado: 409.
- **Pós-condições:** Metadados atualizados; saldo preservado.
- **Requisito:** RF005.

## UC06 — Consultar e filtrar

- **Objetivo:** Localizar produtos.
- **Ator principal:** Administrador de estoque.
- **Pré-condições:** Sessão ativa.
- **Fluxo principal:** Abrir Produtos; informar texto/categoria/estoque baixo; consultar lista e contagem.
- **Fluxos alternativos:** Filtros vazios exibem todos os ativos; nenhum resultado exibe estado vazio.
- **Exceções:** Falha de rede apresenta mensagem e opção de tentar novamente.
- **Pós-condições:** Nenhum dado é alterado.
- **Requisito:** RF006.

## UC07 — Registrar entrada

- **Objetivo:** Aumentar saldo.
- **Ator principal:** Administrador de estoque.
- **Pré-condições:** Sessão ativa e produto ativo.
- **Fluxo principal:** Nova movimentação; escolher produto e Entrada; quantidade e motivo; salvar; confirmar saldo.
- **Fluxos alternativos:** Motivo de correção documenta entrada compensatória; cancelar não grava.
- **Exceções:** Quantidade inválida ou saldo acima do limite: 400, sem alteração.
- **Pós-condições:** Saldo acrescido e evento com usuário, data e saldo final.
- **Requisito:** RF007.

## UC08 — Registrar saída

- **Objetivo:** Reduzir saldo com controle.
- **Ator principal:** Administrador de estoque.
- **Pré-condições:** Sessão ativa e produto ativo.
- **Fluxo principal:** Nova movimentação; escolher Saída e produto; informar quantidade e motivo; salvar.
- **Fluxos alternativos:** Quantidade igual ao saldo zera estoque; cancelar não grava.
- **Exceções:** Saldo insuficiente: 400; transação é desfeita, sem evento parcial.
- **Pós-condições:** Saldo reduzido, nunca negativo, e histórico gravado.
- **Requisito:** RF008.

## UC09 — Consultar histórico

- **Objetivo:** Auditar registros recentes.
- **Ator principal:** Administrador de estoque.
- **Pré-condições:** Sessão ativa.
- **Fluxo principal:** Abrir Movimentações; consultar eventos mais recentes, datas, motivos, usuário e saldo após.
- **Fluxos alternativos:** Sem eventos exibe estado vazio; produto arquivado continua aparecendo.
- **Exceções:** Sessão expirada: 401; erro de carga pode ser repetido.
- **Pós-condições:** Histórico exibido sem alteração.
- **Requisito:** RF009.

## UC10 — Arquivar produto

- **Objetivo:** Retirar item descontinuado do catálogo.
- **Ator principal:** Administrador de estoque.
- **Pré-condições:** Sessão ativa, produto ativo e saldo zero.
- **Fluxo principal:** Abrir Produtos; Arquivar; confirmar diálogo; remover da lista ativa.
- **Fluxos alternativos:** Cancelar mantém o produto ativo.
- **Exceções:** Saldo positivo ou produto inativo/inexistente: 400.
- **Pós-condições:** Produto inativo; código e eventos preservados.
- **Requisito:** RF010.

## UC11 — Consultar painel

- **Objetivo:** Avaliar posição atual e reposição.
- **Ator principal:** Administrador de estoque.
- **Pré-condições:** Sessão ativa.
- **Fluxo principal:** Abrir Visão geral; ler totais, alertas e eventos; navegar para detalhes.
- **Fluxos alternativos:** Sem produtos: totais zero e estados vazios; sem alertas: mensagem positiva.
- **Exceções:** Sessão inválida exige login; falha de rede informa erro.
- **Pós-condições:** Indicadores exibidos; nenhum saldo é alterado.
- **Requisito:** RF011.

## UC12 — Exportar CSV

- **Objetivo:** Analisar estoque em planilha.
- **Ator principal:** Administrador de estoque.
- **Pré-condições:** Sessão ativa.
- **Fluxo principal:** Abrir Relatórios; baixar CSV; navegador recebe arquivo; abrir em planilha compatível.
- **Fluxos alternativos:** Catálogo vazio produz cabeçalho sem linhas; botão do painel exporta o mesmo conteúdo.
- **Exceções:** Sem sessão: 401 e solicitação de login; erro de download informa falha.
- **Pós-condições:** Arquivo gerado com os produtos ativos e sem alteração do banco.
- **Requisito:** RF012.



## UC13 — Cadastrar usuário local

- **Objetivo:** obter acesso ao estoque local do negócio.
- **Ator principal:** novo usuário.
- **Pré-condições:** aplicação iniciada em loopback; sem necessidade de sessão anterior.
- **Fluxo principal:** selecionar Cadastro; informar usuário, senha e confirmação; enviar; validar e persistir hash; criar sessão; abrir painel com o nome da conta.
- **Fluxos alternativos:** voltar à aba Entrar sem cadastrar; corrigir campos e tentar novamente; posteriormente sair e entrar com a nova conta.
- **Exceções:** nome já cadastrado, senha curta ou confirmação divergente retornam erro sem inserir usuário; tentativa de origem cruzada retorna 403; limite de tentativas retorna 429; servidor fora de loopback recusa cadastro.
- **Pós-condições:** usuário persistido e sessão autenticada com acesso ao mesmo estoque dos demais usuários.
- **Requisito:** RF013.
