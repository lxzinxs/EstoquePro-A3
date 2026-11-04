> **Atualização:** o backend principal agora usa Django/PostgreSQL e a marca continua EstoquePro. Leia o adendo [MIGRACAO_DJANGO.md](MIGRACAO_DJANGO.md) e o [DER atual](diagramas/django-er.mmd). O conteúdo a seguir documenta a primeira versão SQLite e permanece como histórico para adaptação ao template oficial.

# EstoquePro — documento acadêmico provisório

**Disciplina:** Projeto e Engenharia de Software — A3. **Versão:** MVP local de 03/11/2026. **Instituição, professor, turma, integrantes, matrículas e responsabilidades nominais:** não informados. Este documento organiza o conteúdo; precisa ser adaptado ao template oficial e revisado contra o PDF antes da entrega.

## Introdução, problema e justificativa

O controle de estoque é uma atividade recorrente de pequenos negócios. Registros dispersos dificultam saber quanto há de cada produto e por que um saldo foi alterado. O EstoquePro oferece um catálogo centralizado com transações de entrada e saída, histórico e sinalização de reposição. A relevância acadêmica está na ligação verificável entre requisitos, regras de negócio, modelagem, implementação e testes.

## Objetivos e público-alvo

Oferecer uma ferramenta local, simples e verificável para o administrador de estoque de um pequeno negócio. Os objetivos específicos são organizar o catálogo, rastrear movimentações, impedir inconsistências de saldo, localizar itens em falta e exportar a posição atual. A aplicação não substitui sistemas fiscais ou contábeis. Escopo, critérios de aceitação e limitações estão em [planejamento](planejamento.md).

## Engenharia de requisitos e casos de uso

Foram definidos 13 requisitos funcionais e 12 não funcionais em [requisitos](requisitos.md), com prioridades, entradas, processamento, saídas, regras e critérios verificáveis. Os [13 casos de uso](casos-de-uso.md) descrevem pré-condições, fluxo principal, alternativas, exceções e pós-condições. Os atores são o usuário de estoque (mesmas permissões do administrador) e o novo usuário que cadastra conta local.

## Modelagem e arquitetura

As fontes de casos de uso (PlantUML), classes reais (Mermaid), sequência, atividades e componentes estão em [diagramas](diagramas/README.md). O [DER](diagramas/der.mmd) corresponde ao esquema executado. Não foram criadas classes fictícias de entidade para corresponder artificialmente ao modelo relacional: `Inventory` retorna dicionários de linhas, `Handler` trata HTTP e `Application` administra sessões e conexões de atendimento.

A separação entre interface, controlador, serviço/repositório e banco permite testar regras sem navegador e testar integração por HTTP. O saldo corrente e o histórico são atualizados em uma transação SQLite; o bloqueio de escrita precede a leitura do saldo para evitar saídas simultâneas inconsistentes.

## Modelo de dados e implementação

Cinco tabelas: usuários, categorias, fornecedores, produtos e movimentações. Produtos pertencem a uma categoria e podem ter fornecedor; cada movimentação pertence a um produto e registra usuário, quantidade, tipo, motivo, data UTC e saldo final. Chaves estrangeiras, unicidade e restrições numéricas reforçam o domínio. Preços usam centavos inteiros. `schema.sql` inicializa a versão 1 sem apagar dados; ainda não há migrações incrementais necessárias para versões posteriores.

A implementação usa Python 3.12, SQLite e HTML/CSS/JavaScript nativos. Não há dependências externas na aplicação. Autenticação usa PBKDF2 com salt, cookie HttpOnly e sessões em memória. Alterações exigem CSRF; exportação neutraliza fórmulas de planilha. O [manual](operacao.md) detalha API, instalação, segurança, backup e recuperação.

## Interface e protótipos

O layout adota azul-marinho, azul e ciano como referência à marca enviada. Login, navegação, indicadores, tabelas e formulários dialogam com os fluxos reais. As [capturas de interface](prototipos/README.md) foram produzidas pelo teste de navegador, em desktop e celular, usando apenas dados fictícios. O logotipo original permanece pendente como arquivo incorporável. Não foi realizada pesquisa formal de usabilidade com usuários.

## Testes e evidências

Os testes de unidade e integração cobrem validação, cadastro, consulta, edição, arquivamento, persistência, autenticação, CSRF, saldo insuficiente, concorrência e exportação. O teste Playwright realiza o fluxo de interface, incluindo erro de saída e download. Resultados efetivamente executados, dificuldades e limites estão em [resultado dos testes](testes/resultado.md). Não se afirma cobertura percentual ou homologação em navegadores que não foram testados.

## Gerenciamento e histórico

O [backlog](../backlog/backlog.csv) relaciona requisitos e tarefas, com status, papéis, sprint e prazo. Responsáveis são papéis propostos, pois nomes não foram fornecidos. A data da Sprint 1 é anterior ao início constatado; sua entrega não foi presumida. O trabalho local foi desenvolvido a partir de checkout sem commits e sem código; nenhum push foi realizado. O histórico de Git só comprova commits que efetivamente existirem, e não deve ser confundido com entregas retroativas de sprint.

## Dificuldades e soluções

- Ausência de PDF/template: iniciar MVP por autorização posterior do solicitante; manter documento provisório e checklist de pendências.
- Checkout vazio: criar estrutura desde o início, preservando a configuração Git existente.
- Restrição de sockets no executor: executar testes locais com permissão de execução adequada; não substituir testes HTTP por verificações triviais.
- Rótulos de seletores incluíam conteúdo das opções no nome acessível: explicitar os nomes e repetir o teste completo de interface.
- Escritas concorrentes: iniciar transação imediata antes de ler o saldo; testar duas saídas sobre saldo limitado.

## Considerações finais

O MVP realiza o ciclo de catálogo e estoque com persistência e trilha de movimentações, acompanhado de testes e materiais de demonstração. A validação acadêmica final depende do PDF, template, revisão dos integrantes e confirmação da apresentação. Evoluções possíveis após o escopo atual incluem perfis de permissão, paginação, múltiplos depósitos, incorporação do arquivo original da marca e recuperação de senha; não são funcionalidades entregues.

## Referências técnicas

Fontes técnicas utilizadas como referência de APIs e formatos (não substituem a bibliografia e o padrão exigidos pelo professor):

- Python Software Foundation. Documentação Python: [sqlite3](https://docs.python.org/3/library/sqlite3.html), [http.server](https://docs.python.org/3/library/http.server.html), [unittest](https://docs.python.org/3/library/unittest.html), [hashlib](https://docs.python.org/3/library/hashlib.html).
- SQLite. [Transactions](https://sqlite.org/lang_transaction.html) e [Online Backup API](https://sqlite.org/backup.html).
- MDN Web Docs. [Fetch API](https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API) e [dialog](https://developer.mozilla.org/en-US/docs/Web/HTML/Element/dialog).
- Playwright. [Python documentation](https://playwright.dev/python/).
- Mermaid. [Diagram syntax](https://mermaid.js.org/intro/syntax-reference.html).
- PlantUML. [Use case diagram](https://plantuml.com/use-case-diagram).

Não foram inventados artigos, entrevistas, integrantes, parecer do professor ou datas de consulta a documentos indisponíveis.

## Checklist provisório de conformidade A3

| Item do texto recebido | Evidência | Situação |
|---|---|---|
| Software executável e persistente | src/, database/, README, testes | Implementado e validado localmente |
| Código completo e organizado | Separação domínio/HTTP/interface | Preparado no checkout |
| ≥8 requisitos funcionais e RNF | 13 RF e 12 RNF | Documentado |
| Casos de uso e fluxos alternativos | 13 UC | Documentado |
| UML e modelo de dados | Fontes PlantUML/Mermaid e esquema SQLite | Produzido para o MVP |
| Interface e protótipos | Capturas desktop/mobile | Produzido |
| Testes automatizados | unittest e Playwright | Resultado no relatório de testes |
| Instalação, execução e backup | README e manual | Documentado e verificado |
| Backlog e rastreabilidade | backlog.csv e requisitos | Preparado; revisão nominal pendente |
| Apresentação e demonstração | apresentacao/ | Roteiro preparado, apresentação ao professor não realizada |
| Integrantes e responsabilidades | Não fornecidos | Pendente |
| PDF oficial e aprovação do tema | Não fornecidos | Conformidade oficial não verificável |
| Template oficial | Não fornecido | Adaptação final pendente |
| Data sorteada da apresentação | Não fornecida | Pendente |
| Entrega no GitHub/atividade | Sem push ou submissão | Depende de autorização e ação posterior |
