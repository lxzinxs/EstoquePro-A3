# Dois planos — proposta atual

Substitui os quatro planos anteriores. O catálogo é funcional; contratação, cobrança, expiração e restrições ainda não estão ativas. Recursos marcados como planejados continuam pendentes.

| Plano | Preço total | Duração | Contas / produtos |
|---|---:|---|---|
| Básico | R$ 0 | Somente 1 mês | 1 / 50 |
| Completo mensal | R$ 150 | 1 mês | Ilimitados |
| Completo semestral | R$ 750 | 6 meses | Ilimitados |
| Completo anual | R$ 1.500 | 12 meses | Ilimitados |

São **dois planos**, sendo três modalidades de pagamento do mesmo Completo. Semestral e anual equivalem a R$125/mês, com pagamento total do período; economia de R$150/semestre e R$300/ano em relação ao mensal. Não é parcelamento nem cobrança já habilitada.

## Condições de cancelamento propostas

Pedido recebido: semestral sem cancelamento após dois meses de uso e anual após três meses. A tela apresenta esses prazos como condições propostas de encerramento antecipado do período contratado, mantendo a possibilidade de desativar a renovação. Política de reembolso, proporcionalidade, direito de arrependimento e demais obrigações legais precisam de definição contratual e revisão antes da venda. Não existe bloqueio de cancelamento ou cobrança no sistema atual. Não foram inventados termos definitivos de reembolso para mensal, semestral ou anual.

O período gratuito será de um mês de calendário; não deve renovar gratuitamente nem gerar cobrança automática. Nesta revisão, essa duração é declarada no catálogo, mas **não há expiração aplicada às contas atuais**.

## Recursos

### Básico

- Cadastro de itens — disponível no aplicativo atual.
- Entradas e saídas — disponível no aplicativo atual.
- Alertas de estoque baixo — disponível no aplicativo atual.
- Relatório básico CSV — disponível no aplicativo atual.
- Acesso multidispositivo — planejado.
- Backup na conta Google do usuário — planejado.
- Suporte por e-mail — planejado.

### Completo

Inclui tudo do Básico, mais:

- Análise financeira com filtro por período — planejado.
- Cadastro de fornecedores — disponível no aplicativo atual.
- Pedidos de compra: Pendente → Recebido — planejado.
- Cobertura de estoque em dias — planejado.
- Movimentação em lote — planejado.
- Custo médio ponderado — planejado.
- Histórico completo de cada item — planejado.
- Exportação Excel e PDF — planejado.
- Validade por lote e saída FEFO — planejado.
- Suporte prioritário via WhatsApp — planejado.
- Empresas com dados isolados — planejado.
- Transferências entre filiais com confirmação — planejado.
- Múltiplos locais de estoque — planejado.
- Múltiplos pontos de atendimento — planejado.
- Sugestões de compra por regras locais — planejado.
- Importação por XML da NF-e — planejado.
- Curva ABC automática — planejado.
- Resumo executivo diário — planejado.
- Admin Master e gestão de usuários — planejado.
- Permissões Membro, Admin e Master — planejado.
- Auditoria completa por usuário — planejado.
- Sincronização em tempo real — planejado.
- Código de barras no cadastro e movimentação — planejado.
- Exportação ABC e sugestões em PDF/Excel — planejado.
- Notificações de transferência em tempo real — planejado.
- WhatsApp premium e onboarding personalizado gratuito — planejado.
- Contas a pagar, receber e fluxo de caixa — planejado.
- NF-e gera conta a pagar automaticamente — planejado.
- Pedido em um clique e compartilhamento por WhatsApp — planejado.
- Cotação com até 3 fornecedores e histórico de preços — planejado.
- Inventário cíclico com leitor e contagem cega — planejado.
- Impressão de etiquetas de código de barras — planejado.
- Logo do negócio em relatórios e PDFs — planejado.
- Resumo mensal em PDF e semanal por WhatsApp — planejado.

## Implementação necessária antes de ativar planos

1. **Organizações, assinatura e isolamento:** criar organizações separadas do cadastro de usuário, associação de membros e migração transacional de todos os dados atuais para uma organização legada. Acrescentar escopo de organização/empresa a toda consulta, evento, backup e exportação. Validar acesso cruzado em testes antes de habilitar criação de empresas. Cadastro público atual não cria organizações isoladas.
2. **Limites e permissões no backend:** validar quota de usuários e produtos atomicamente, não apenas ocultar botões. Master gerencia membros, Admin gerencia operação e Membro movimenta estoque. Impedir remoção do último Master. Downgrade acima da quota não apaga dados: restringir novos cadastros até adequação. Sem inventar cobrança ou ativar planos pagos por uma requisição livre do navegador.
3. **Business:** registrar custo histórico separado do preço de referência; custo médio ponderado por entrada, sem aritmética float. Pedidos têm linhas e recebimento idempotente em transação. Lotes armazenam saldo e validade; FEFO consome primeiro o lote válido com menor vencimento. Operações em lote são atômicas; nenhuma linha deve deixar saldo parcial em caso de erro. Histórico completo precisa de paginação e filtro por item. Exportação XLSX deve produzir arquivo Excel válido; PDF deve ser PDF real ou impressão claramente identificada.
4. **Plus:** locais e pontos de atendimento pertencem a empresa. Transferências reservam na origem e creditam no destino somente após confirmação, sem dupla confirmação. Sugestões de compra usam regras gratuitas: demanda média diária, prazo de reposição e estoque de segurança. Curva ABC usa valor movimentado no período; itens sem histórico não recebem previsão inventada. XML NF-e exige parser seguro, limite de tamanho, validação de chave, deduplicação e correspondência de itens; não buscar entidades externas. Auditoria registra ator e alterações. Tempo real requer eventos autenticados por organização e reconexão; não anunciar “sincronização ilimitada” por simplesmente recarregar tela.
5. **Pro:** lançamentos financeiros por competência/vencimento e baixas parciais, com fluxo de caixa por período. Importar NF-e gera títulos sem duplicar notas já importadas. Cotações limitadas a três fornecedores por rodada; histórico de preços preservado. Inventário cego oculta saldo esperado até fechamento autorizado e gera ajuste auditado. Etiquetas e relatórios devem respeitar a marca da organização. Resumos têm agendamento, fuso e histórico de execução.
6. **Integrações e suporte:** backup Google por OAuth do próprio usuário, consentimento revogável e armazenamento seguro de refresh token por organização; nunca gravar credenciais no Git. Exige configuração de aplicativo Google e destinos de rede. Acesso multidispositivo depende de hospedagem HTTPS com autenticação segura, não de expor o servidor `http.server` publicamente. WhatsApp por link de compartilhamento pode ser gratuito e exige confirmação manual; envio automático/agendado depende de API e pode ter custo. IA generativa paga foi excluída; recomendações por regras não serão rotuladas como IA generativa.

## Aceitação para lançamento

Básico deve expirar após um mês de calendário desde a ativação, mantendo acesso à conta, contratação e exportação dos próprios dados, sem conversão automática em plano pago. Quotas básicas propostas: 1 conta e 50 produtos. Completo não terá quota comercial. Bloqueio de novos cadastros deve ser transacional e preservar dados existentes. As regras de expiração, autorização, cobrança, renovação e cancelamento precisam ser implementadas e testadas no backend antes de lançamento comercial.
