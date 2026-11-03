# Planejamento — EstoquePro

## Identificação e problema

Sistema de Gerenciamento de Estoque. Pequenos negócios que registram entradas e saídas de modo informal podem perder a visão de disponibilidade, comprar tarde demais e não conseguir explicar alterações de saldo. A solução centraliza o catálogo, aplica validações e registra cada movimentação.

**Justificativa:** um fluxo curto de cadastro e movimentação permite demonstrar requisitos, arquitetura, transações, rastreabilidade e testes em um projeto compatível com a A3.

**Objetivo geral:** disponibilizar uma aplicação web local que registre e consulte o estoque de forma consistente.

**Objetivos específicos:** cadastrar produtos e seus vínculos; impedir códigos duplicados e saídas acima do saldo; sinalizar reposição; preservar o histórico; exportar a posição atual; permitir reprodução da instalação e dos testes.

**Público-alvo:** responsável pelo estoque de um pequeno comércio, representado por um administrador. A aprovação formal do tema pelo professor ainda não foi documentada; o tema foi inferido do nome e da identidade visual enviados pelo solicitante.

## Escopo e aceitação

Incluído: autenticação local, categorias e fornecedores por nome, produtos, edição de metadados, arquivamento, entradas, saídas, painel, histórico recente, filtros, relatório CSV e backup técnico.

Fora do escopo: vendas, notas fiscais, contabilidade, pedidos de compra, múltiplas empresas, múltiplos depósitos, lotes, validade, código de barras por câmera, permissões por perfil e envio de notificações. O ícone de caixa da interface é uma representação própria inspirada nas cores da referência; o arquivo original da marca não foi incorporado como ativo local.

Aceitação do MVP: usuário entra, cadastra categoria e produto, registra entrada e saída, vê o saldo atualizado, recebe erro ao exceder o saldo, exporta CSV e encontra os dados após reiniciar. Os testes precisam verificar regras, API e fluxo real de interface.

## Ambiente e decisões técnicas

- Python 3.12+, biblioteca padrão (`http.server`, `sqlite3`, `unittest`, `hashlib`). A escolha reduz instalação e facilita a demonstração local.
- HTML semântico, CSS responsivo e JavaScript nativo. Navegação por hash; requisições com Fetch; saída de conteúdo escapada.
- SQLite com chaves estrangeiras, WAL, transações e versão inicial do esquema (`user_version=1`). Uma máquina e baixo volume de escrita concorrente.
- Teste de interface opcional com Playwright/Chromium. Node é opcional para conferir a sintaxe do JavaScript.

Não há build ou serviço de banco separado. A execução do Python entrega interface e API na mesma origem, em loopback. O modo demo cria dados fictícios idempotentemente; não substitui dados existentes.

## Arquitetura e responsabilidades

1. Interface (`static/`): apresentação, formulários, filtros locais, feedback e download.
2. Controlador HTTP (`server.py`): roteamento, limites de corpo, sessão, CSRF, códigos HTTP e CSV.
3. Serviço de domínio/repositório (`Inventory` em `domain.py`): validação, consultas e transações.
4. SQLite (`schema.sql`): integridade relacional e persistência.

`Inventory.move` adquire uma transação `BEGIN IMMEDIATE`, lê o saldo atual, valida, atualiza e grava a movimentação na mesma transação. Exceções causam rollback. Não existe endpoint para alterar diretamente o saldo ou apagar histórico. A arquitetura intencionalmente reúne serviço e repositório em uma classe pequena para manter o projeto acadêmico compreensível.

Limitações: somente unidades inteiras; nomes podem ser buscados na interface sem distinção de maiúsculas, enquanto o `lower` do SQLite é limitado em caracteres não ASCII; nomes únicos no banco usam a collation NOCASE padrão do SQLite. Histórico na interface limitado aos últimos 200 eventos; banco mantém todos. Sem migração incremental além da inicialização da versão 1, sem paginação de catálogo e sem garantia de desempenho para bases extensas.

## Cronograma informado e situação

| Marco | Data informada | Situação |
|---|---|---|
| Sprint 1 | 21/10/2026 | Data anterior ao início; não há evidência de entrega |
| Início desta implementação | 03/11/2026 | Implementação e validação local registradas |
| Sprint 2, software e documentação | 18/11/2026 | MVP preparado; adequação oficial e revisão da equipe pendentes |
| Apresentação | 18/11 ou 24/11/2026 | Depende do sorteio não fornecido |

Plano restante sugerido: 04–08/11 validar PDF/template e revisar requisitos; 09–13/11 revisão dos integrantes e ajustes exigidos; 14–17/11 ensaio, revisão documental e backup; 18/11 entrega pelo responsável. É planejamento proposto, não comprovação de execução futura.

Integrantes e distribuição nominal de responsabilidades: a informar. Papéis necessários: requisitos, desenvolvimento, testes, documentação e apresentação; não foram atribuídos a pessoas fictícias.
