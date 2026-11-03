# Interface e protótipos executáveis

A interface real funciona como protótipo de alta fidelidade em `src/estoquepro/static/`. As capturas deste diretório são geradas pelo teste de navegador, usando dados fictícios e um banco temporário.

- `cadastro-desktop.png`: aba de cadastro com usuário, senha e confirmação.
- `dashboard-desktop.png`: painel em 1440 px, menu lateral, indicadores, alertas e catálogo.
- `dashboard-mobile.png`: painel em 390 px, menu horizontal e tabelas com rolagem interna.
- `movimentacoes-desktop.png`: histórico depois de entrada e saída realizadas pelo teste.

Fluxo: Entrar / Cadastro → Visão geral → Categorias/Fornecedores → Produtos → Movimentações → Relatórios. Formulários usam diálogo modal com validação nativa e mensagens da API. Dados dinâmicos são escapados antes de inserção no DOM; mensagens de status usam regiões acessíveis. Teste de navegador verifica ausência de rolagem horizontal na página móvel; isso não equivale a uma auditoria completa WCAG.

Direção visual: azul-marinho, azul e ciano inspirados na imagem do EstoquePro enviada pelo solicitante; verde/âmbar/vermelho também têm rótulos de texto para comunicar status. O arquivo original do logo não estava disponível no filesystem e permanece pendente de incorporação como ativo, caso necessário.
