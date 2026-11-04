# Planos e evolução funcional

Preços iniciais propostos em 04/11/2026. Não há assinatura, cobrança, contratação de serviço ou mudança automática de permissões. Valores sujeitos à revisão de custos de hospedagem, armazenamento, impostos e capacidade de atendimento antes da comercialização. O suporte descrito é uma proposta comercial: não há equipe, e-mail ou WhatsApp de suporte configurados.

| Plano | Mensalidade proposta | Contas | Produtos |
|---|---:|---:|---:|
| Grátis | R$ 0 | 1 | 50 |
| Business | R$ 49,90 | 2 | 100 |
| Plus | R$ 99,90 | 5 | 300 |
| Pro | R$ 199,90 | Ilimitadas | Ilimitados |

Hierarquia cumulativa: Grátis → Business → Plus → Pro. As repetições e prefixos `svg` do texto recebido foram removidos. Contas significam usuários ativos por organização; produtos significam itens ativos somados entre as empresas da organização. Essa definição é proposta e ainda não é aplicada no banco. “Ilimitados” significa ausência de quota comercial, sem promessa de capacidade física infinita.

## Entregue nesta revisão

Página de comparação com identidade própria, acessível antes de entrar e dentro do aplicativo. Fonte única de dados em `src/estoquepro/plans.py`, exposta por GET `/api/plans`. A página identifica recursos existentes e planejados; limites propostos e cobrança desativada são explícitos. Nada foi bloqueado retroativamente: fornecedores continuam acessíveis e os usuários existentes continuam no mesmo estoque compartilhado.

**Esta revisão não implementa os módulos avançados abaixo nem transforma a aplicação local em um SaaS multiempresa.** A página não tem botão de contratar que simule um upgrade inexistente.

## Matriz funcional solicitada

### Grátis

| Grupo | Funcionalidade | Situação |
|---|---|---|
| Estoque | Cadastro de itens | Disponível no app atual (sem restrição por plano) |
| Estoque | Entradas e saídas | Disponível no app atual (sem restrição por plano) |
| Estoque | Alertas de estoque baixo | Disponível no app atual (sem restrição por plano) |
| Relatórios | Relatório básico CSV | Disponível no app atual (sem restrição por plano) |
| Acesso | Acesso multidispositivo | Pendente de implementação/configuração |
| Integrações | Backup na conta Google do usuário | Pendente de implementação/configuração |
| Atendimento | Suporte por e-mail | Pendente de implementação/configuração |

### Business

Inclui o plano anterior.

| Grupo | Funcionalidade | Situação |
|---|---|---|
| Gestão | Análise financeira com filtro por período | Pendente de implementação/configuração |
| Gestão | Cadastro de fornecedores | Disponível no app atual (sem restrição por plano) |
| Compras | Pedidos de compra: Pendente → Recebido | Pendente de implementação/configuração |
| Estoque | Cobertura de estoque em dias | Pendente de implementação/configuração |
| Estoque | Movimentação em lote | Pendente de implementação/configuração |
| Custos | Custo médio ponderado | Pendente de implementação/configuração |
| Estoque | Histórico completo de cada item | Pendente de implementação/configuração |
| Relatórios | Exportação Excel e PDF | Pendente de implementação/configuração |
| Estoque | Validade por lote e saída FEFO | Pendente de implementação/configuração |
| Atendimento | Suporte prioritário via WhatsApp | Pendente de implementação/configuração |

### Plus

Inclui o plano anterior.

| Grupo | Funcionalidade | Situação |
|---|---|---|
| Multiempresa | Empresas com dados isolados | Pendente de implementação/configuração |
| Multiempresa | Transferências entre filiais com confirmação | Pendente de implementação/configuração |
| Multiempresa | Múltiplos locais de estoque | Pendente de implementação/configuração |
| Multiempresa | Múltiplos pontos de atendimento | Pendente de implementação/configuração |
| Automação sem IA paga | Sugestões de compra por regras locais | Pendente de implementação/configuração |
| Automação sem IA paga | Importação por XML da NF-e | Pendente de implementação/configuração |
| Automação sem IA paga | Curva ABC automática | Pendente de implementação/configuração |
| Automação sem IA paga | Resumo executivo diário | Pendente de implementação/configuração |
| Equipe e segurança | Admin Master e gestão de usuários | Pendente de implementação/configuração |
| Equipe e segurança | Permissões Membro, Admin e Master | Pendente de implementação/configuração |
| Equipe e segurança | Auditoria completa por usuário | Pendente de implementação/configuração |
| Equipe e segurança | Sincronização em tempo real | Pendente de implementação/configuração |
| Avançado | Código de barras no cadastro e movimentação | Pendente de implementação/configuração |
| Avançado | Exportação ABC e sugestões em PDF/Excel | Pendente de implementação/configuração |
| Avançado | Notificações de transferência em tempo real | Pendente de implementação/configuração |
| Atendimento | WhatsApp premium e onboarding personalizado gratuito | Pendente de implementação/configuração |

### Pro

Inclui o plano anterior.

| Grupo | Funcionalidade | Situação |
|---|---|---|
| Financeiro | Contas a pagar, receber e fluxo de caixa | Pendente de implementação/configuração |
| Financeiro | NF-e gera conta a pagar automaticamente | Pendente de implementação/configuração |
| Compras | Pedido em um clique e compartilhamento por WhatsApp | Pendente de implementação/configuração |
| Compras | Cotação com até 3 fornecedores e histórico de preços | Pendente de implementação/configuração |
| Estoque | Inventário cíclico com leitor e contagem cega | Pendente de implementação/configuração |
| Estoque | Impressão de etiquetas de código de barras | Pendente de implementação/configuração |
| Marca | Logo do negócio em relatórios e PDFs | Pendente de implementação/configuração |
| Executivo | Resumo mensal em PDF e semanal por WhatsApp | Pendente de implementação/configuração |

## Implementação necessária antes de ativar planos

1. **Organizações, assinatura e isolamento:** criar organizações separadas do cadastro de usuário, associação de membros e migração transacional de todos os dados atuais para uma organização legada. Acrescentar escopo de organização/empresa a toda consulta, evento, backup e exportação. Validar acesso cruzado em testes antes de habilitar criação de empresas. Cadastro público atual não cria organizações isoladas.
2. **Limites e permissões no backend:** validar quota de usuários e produtos atomicamente, não apenas ocultar botões. Master gerencia membros, Admin gerencia operação e Membro movimenta estoque. Impedir remoção do último Master. Downgrade acima da quota não apaga dados: restringir novos cadastros até adequação. Sem inventar cobrança ou ativar planos pagos por uma requisição livre do navegador.
3. **Business:** registrar custo histórico separado do preço de referência; custo médio ponderado por entrada, sem aritmética float. Pedidos têm linhas e recebimento idempotente em transação. Lotes armazenam saldo e validade; FEFO consome primeiro o lote válido com menor vencimento. Operações em lote são atômicas; nenhuma linha deve deixar saldo parcial em caso de erro. Histórico completo precisa de paginação e filtro por item. Exportação XLSX deve produzir arquivo Excel válido; PDF deve ser PDF real ou impressão claramente identificada.
4. **Plus:** locais e pontos de atendimento pertencem a empresa. Transferências reservam na origem e creditam no destino somente após confirmação, sem dupla confirmação. Sugestões de compra usam regras gratuitas: demanda média diária, prazo de reposição e estoque de segurança. Curva ABC usa valor movimentado no período; itens sem histórico não recebem previsão inventada. XML NF-e exige parser seguro, limite de tamanho, validação de chave, deduplicação e correspondência de itens; não buscar entidades externas. Auditoria registra ator e alterações. Tempo real requer eventos autenticados por organização e reconexão; não anunciar “sincronização ilimitada” por simplesmente recarregar tela.
5. **Pro:** lançamentos financeiros por competência/vencimento e baixas parciais, com fluxo de caixa por período. Importar NF-e gera títulos sem duplicar notas já importadas. Cotações limitadas a três fornecedores por rodada; histórico de preços preservado. Inventário cego oculta saldo esperado até fechamento autorizado e gera ajuste auditado. Etiquetas e relatórios devem respeitar a marca da organização. Resumos têm agendamento, fuso e histórico de execução.
6. **Integrações e suporte:** backup Google por OAuth do próprio usuário, consentimento revogável e armazenamento seguro de refresh token por organização; nunca gravar credenciais no Git. Exige configuração de aplicativo Google e destinos de rede. Acesso multidispositivo depende de hospedagem HTTPS com autenticação segura, não de expor o servidor `http.server` publicamente. WhatsApp por link de compartilhamento pode ser gratuito e exige confirmação manual; envio automático/agendado depende de API e pode ter custo. IA generativa paga foi excluída; recomendações por regras não serão rotuladas como IA generativa.

## Aceitação para lançamento

- Grátis recusa o 51º produto e o 2º membro; Business recusa o 101º e o 3º; Plus recusa o 301º e o 6º. Pro não tem quota comercial. Tentativas concorrentes não ultrapassam limites.
- Dados de organizações distintas não aparecem em consultas, transferências, eventos, exports ou backups. Troca de empresa não altera permissões.
- Recurso pago não executa pela API quando não autorizado, inclusive chamando endpoint diretamente.
- Recebimentos, transferência, NF-e e jobs são idempotentes. Falha desfaz transações sem perda de saldo.
- Backup/restauração, permissões e histórico são testados por organização, incluindo migração do banco existente.
- Publicação comercial só após validar integrações, capacidade operacional e atendimento real; preços não incluem serviços externos já contratados.
