# EstoquePro — migração Django/PostgreSQL

A marca acadêmica permanece **EstoquePro** por solicitação do usuário. Não houve renomeação do repositório. O servidor Python/SQLite anterior é preservado em `src/estoquepro/server.py` apenas como legado; a nova aplicação é `manage.py` + `config/` + `inventory/`.

## Stack e execução

- Django 5.2 LTS, autenticação e migrações nativas, sessões em PostgreSQL.
- PostgreSQL 17: testes e validação executados no banco real, não em SQLite.
- HTML/CSS/JavaScript nativos com templates Django; requisições de alteração exigem CSRF.
- Gunicorn para servir o backend em produção; `runserver` somente para desenvolvimento/apresentação.
- Worker separado com fila persistente PostgreSQL, `SELECT FOR UPDATE SKIP LOCKED`, scheduler, retentativas e recuperação de tarefas de exportação após timeout.
- Exportação real XLSX (openpyxl), PDF (ReportLab) e XML seguro (defusedxml).

Instalação e comandos atualizados no README. `scripts/dev.py` funciona por argumentos em bash, fish e PowerShell; não exige sintaxe de variável de um shell específico. Usa Docker local para PostgreSQL e credenciais aleatórias em `data/`, ignoradas no Git. O container/volume local tem um identificador interno antigo `nerythstock-postgres`; isso não muda o nome apresentado e preserva o banco existente. Não apague o volume para mudar nomes.

## Modelo de acesso

Cada cadastro público cria **um negócio isolado**, um usuário Master, uma filial e um local. O cadastro público não concede acesso a empresas existentes. A gestão de equipe cria contas vinculadas ao negócio selecionado; nomes globais de usuário precisam ser únicos. Os formulários, consultas, arquivos e serviços validam o negócio. Serviços não dependem de ocultar botões para aplicar permissões.

| Perfil | Escopo |
|---|---|
| Membro | Consulta operacional, entradas/saídas, transferências e contagem (quando o plano permite) |
| Admin | Operações do Membro, cadastros, compras, financeiro e fechamento de contagem |
| Master | Gestão do negócio, equipe, permissões, marca, agendamento e backup |
| Criador | Um único dono global, acesso a todos os negócios e funcionalidades, sem bloqueio por plano/prazo |

O cargo Criador não faz parte das escolhas de cadastro/equipe. `Creator` tem um slot único com restrição no PostgreSQL. Só o comando local `provision_creator` pode provisioná-lo pelo fluxo fornecido. A administração global Django é reservada ao Criador; auditoria e movimentações são somente leitura nessa administração. O dono da infraestrutura/banco continua tendo poderes técnicos: não se promete segurança contra o próprio administrador do servidor.

O usuário **Lxzinxs** foi provisionado no banco desta máquina. A senha fornecida foi recebida em prompt sem eco e armazenada como hash Django; não está no código, comandos salvos ou Git. Em outra máquina, executar o comando e informar a senha novamente. Nunca usar a senha pessoal em documentação ou testes. As credenciais sintéticas dos testes são independentes.

## Implementado e verificável

- Cadastro/login/logout e alteração de senha; proteção de login contra repetição de tentativas por IP, usando identificador derivado por HMAC.
- Recuperação de senha com token nativo Django. Sem SMTP configurado, a interface informa indisponibilidade; testes de envio usam caixa de e-mail em memória.
- Um mês de calendário para o Básico, uma conta e até 50 produtos ativos. Após expirar, consulta/exportação dos dados permanece disponível; escritas são bloqueadas. Não há conversão automática em pagamento.
- Completo sem quota comercial de produtos/usuários; acesso depende de `paid_until`, configurado pelo Criador enquanto não há gateway. Desativação de renovação disponível sem apagar o período já concedido. Não é implementado bloqueio absoluto de cancelamento/reembolso.
- Empresas/negócios isolados com seleção no cabeçalho. Master do Completo cria outro negócio com dados separados e vigência herdada da assinatura de origem. Filiais, locais de estoque e pontos de atendimento dentro de cada negócio.
- Produtos, categorias, fornecedores, código de barras, edição cadastral, busca e arquivamento condicionado a saldo zero (incluindo trânsito).
- Entradas e saídas atômicas com custo médio ponderado; estoque por lote/local, validade e FEFO, sem consumir lotes vencidos. Correções são eventos novos, nunca edição de histórico pela interface operacional.
- Movimentação em lote de até 100 linhas, com rollback do lote completo. A entrada atual usa JSON validado; não foi criada uma planilha visual de edição em lote.
- Pedidos de compra e linhas, workflow Pendente → Recebido, recebimento idempotente com estoque e conta a pagar.
- Cobertura em dias, sugestões de compra por regras gratuitas, Curva ABC por valor de custo consumido no período, sem chamar serviço de IA pago. Transferências não contam como demanda.
- Pedido a partir da sugestão e link WhatsApp para revisão/envio manual pelo usuário. Não há envio automático, contato de suporte inventado ou mensagem enviada pelo agente.
- Transferências com baixa na origem, saldo em trânsito e confirmação idempotente no destino, preservando lote/validade.
- Contas a pagar/receber, pagamentos parciais sem exceder saldo e fluxo de caixa realizado por período.
- Cotações por rodada com até três fornecedores por produto e histórico de preços.
- Inventário cego com leitor de código de barras via teclado/HID; formulário não exibe saldo esperado e ajuste é fechado por Admin/Master.
- Histórico completo paginado, filtro por produto, auditoria por ator, relatórios XLSX/PDF/CSV e etiquetas Code128 em PDF. Fórmulas de planilha são neutralizadas.
- Upload de logo PNG/JPEG, validação de tamanho/dimensões, regravação sem metadados e uso nos PDFs.
- Worker gera relatório, resumo em JSON e cópia de dados do negócio em arquivo privado. Jobs e downloads são isolados por organização; usuários não recebem hashes de senha ou sessões nos arquivos.
- Agendamentos recorrentes por negócio e atualização de transferências via consulta autenticada a cada 15 segundos. **Isso é polling, não sincronização instantânea por WebSocket/SSE.**

## Dados antigos

`import_legacy` cria snapshot SQLite consistente em arquivo temporário e lê a cópia. Não altera/apaga a origem. Importação é atômica e identificada por digest do conteúdo: repetir o mesmo conjunto não duplica produtos ou histórico. Conflito de nome de usuário com conta Django existente interrompe a importação sem sobrescrever credenciais.

Os hashes legados são reconhecidos por um hasher de compatibilidade e atualizados para o hash preferido do Django no próximo login bem-sucedido. Saldo atual é preservado em lote `LEGADO`; eventos antigos são preservados com saldo após a operação em metadados. O sistema antigo não armazenava custos históricos, portanto **custo inicial importado fica zero**, identificado na auditoria; preço de venda não é tratado como custo inventado.

Na máquina atual foram importados 4 produtos e 3 eventos para o negócio de apresentação, preservando 94 unidades. O Criador acessa esse negócio pelo seletor no cabeçalho. O banco SQLite continua no mesmo caminho.

## Backup e recuperação

A tarefa `backup` gera exportação JSON consistente dos dados de negócio, em transação PostgreSQL REPEATABLE READ, sem credenciais. É um artefato privado para consulta/exportação; **não substitui backup integral recuperável do servidor**. Para recuperação de desastre, usar `pg_dump -Fc` e cópia protegida de `data/private`/arquivos e configurações, com retenção e teste de restauração em banco separado. Não restaurar sobre produção sem validar a cópia. O volume Docker não é backup.

O worker precisa permanecer ativo em processo separado. Jobs interrompidos por mais de 30 minutos voltam à fila; as tarefas existentes são geração de arquivos, não operações financeiras/estoque. Até três tentativas por tarefa; falhas são expostas sem imprimir credenciais. Arquivos não são publicados em `/static/` ou URL aberta.

## Desativado ou ainda pendente

Por decisão do solicitante, domínio, SMTP e canais de suporte/WhatsApp permanecem sem configuração. Além disso:

- Backup na conta Google exige aplicativo OAuth, consentimento e proteção de tokens: **a integração Google ainda não foi implementada**, e não há botão fingindo conexão.
- Gateway de pagamento, webhooks idempotentes, contratação, reembolso e condições legais definitivas ainda não foram integrados. Preços são catálogo; o Criador pode conceder vigência manual para homologação.
- Resumos semanais por WhatsApp e envio automático de notificações externas dependem de configuração/provedor e podem ter custo; o compartilhamento manual já funciona.
- Resumos executivos hoje usam relatório PDF de posição/análise e resumo JSON. Não há pacote editorial mensal separado nem briefing enviado automaticamente a e-mail/WhatsApp.
- Não há sincronização instantânea ilimitada; há polling a cada 15 s. Backups externos, retenção automática e recuperação de desastre em hospedagem contratada ainda precisam de implantação.
- Sem homologação fiscal da NF-e, assinatura digital ou consulta SEFAZ. Importação local valida estrutura/chave/deduplicação/itens/duplicatas e usa correspondência cProd; unidades fracionárias não são suportadas.
- Ainda não houve auditoria externa de segurança, teste de carga, SLA comercial ou implantação HTTPS pública. Dockerfile/Compose são preparação; execução local validada usa PostgreSQL em container e Django no ambiente virtual.

Essas pendências impedem afirmar que todos os recursos comerciais estão concluídos ou que o produto está pronto para venda. O MVP Django é demonstrável; o processo de lançamento continua após a apresentação.

## Revisão de usabilidade — acesso, navegação, cadastro e planos

- Entrar/Cadastro usam o estilo visual da primeira versão, com links destacados, layout responsivo e autenticação real Django.
- Menu agrupado por Estoque, Compras, Financeiro e análises, Operações e Configurações; grupos recolhíveis e atalhos filtrados por permissão. Menu móvel abre em painel e preserva espaço para o conteúdo.
- Cabeçalho com negócio selecionado, identidade e perfil. Planos agora recebe o contexto do negócio pela mesma camada de isolamento das outras telas; não mostra aviso de expiração por contexto ausente.
- Produtos podem ser criados sem pré-cadastros: categoria omitida usa/cria Geral no mesmo negócio, fornecedor é opcional e ambos podem ser criados no formulário. A operação é transacional e respeita unicidade/quota. Custos e saldo continuam sendo definidos por movimentação; não se inventa entrada na criação do produto.
- Campos e colunas traduzidos, dicas de preenchimento, opções avançadas recolhidas, atalho Registrar entrada com produto pré-selecionado e seleção automática de local somente quando houver um único local.
- Planos em cartões com períodos mensal/semestral/anual e valores consistentes. A seleção altera apenas a apresentação: não contrata nem cobra.
- Para o Criador, cabeçalho, Planos e Assinatura exibem acesso Completo permanente, sem cobrança/renovação ou vencimento. Isso deriva do privilégio exclusivo do usuário, não altera o plano de outras contas do negócio nem cria uma assinatura paga fictícia. Os recursos externos ainda pendentes continuam pendentes para todos, inclusive para o Criador.
