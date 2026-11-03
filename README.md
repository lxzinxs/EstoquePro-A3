# EstoquePro

Sistema web de gerenciamento de estoque para pequenos negócios. Projeto acadêmico A3 de Projeto e Engenharia de Software, iniciado em 03/10/2026.

## Executar

Requer **Python 3.12 ou superior** e um navegador moderno. A aplicação e os testes de domínio/API usam somente a biblioteca padrão: não há dependências obrigatórias para instalar.

```bash
cd /workspace/EstoquePro-A3
PYTHONPATH=src python -m estoquepro.server --demo
```

Em um computador local, abra o endereço HTTP do servidor na porta **8000**. Login de demonstração: **admin** / **admin123**. O modo demo é restrito à interface de loopback. Na nuvem, a validação é feita com requisições locais; este projeto não publica uma prévia web automaticamente.

No Windows PowerShell, na pasta do projeto:

```powershell
$env:PYTHONPATH = "src"
python -m estoquepro.server --demo
```

O banco é criado em `data/estoquepro.sqlite3` e os dados permanecem após reiniciar. Dados fictícios só são inseridos se categorias, fornecedores, produtos e movimentações estiverem vazios. A senha inicial nunca é substituída em um banco já inicializado. Encerre com Ctrl+C.

Para começar sem dados fictícios, use um banco novo e defina `ESTOQUEPRO_ADMIN_PASSWORD` com 12 a 256 caracteres por um mecanismo seguro do seu ambiente. Execute sem `--demo`; não registre senhas no Git ou em comandos compartilhados. Para separar bancos, use `--database /caminho/arquivo.sqlite3`. Isso não altera a senha de bancos existentes.

## O que funciona

- Login, sessão de oito horas e logout.
- Cadastro de categorias e fornecedores por nome.
- Cadastro, pesquisa e edição de produtos com código único, vínculos, preço e estoque mínimo.
- Entradas e saídas atômicas com motivo, usuário, data e saldo após a operação.
- Bloqueio de saldo negativo; arquivamento de produtos com saldo zero, preservando o histórico.
- Painel, filtro de estoque baixo e exportação CSV do estoque ativo.
- Interface responsiva em português, sem serviços externos de fontes ou scripts.

O preço é de referência; não é um sistema fiscal ou de custeio. Há um único perfil administrador. Não há recuperação de senha, cadastro de usuários, edição de categorias/fornecedores, edição do histórico ou restauração de produto arquivado na interface.

## Testes

```bash
python -m unittest discover -s tests -v
node --check src/estoquepro/static/app.js  # opcional; Node só é necessário para esta verificação
```

Teste de interface opcional, com Playwright e Chromium (o aplicativo não depende deles):

```bash
python -m pip install -r requirements-browser.txt
python -m playwright install chromium
python tests/browser_smoke.py
# Ou Chromium do sistema:
CHROMIUM_PATH=/usr/bin/chromium python tests/browser_smoke.py
```

O teste de navegador usa um banco temporário e gera capturas em `docs/prototipos/`. Os testes não usam o banco de desenvolvimento. Ambientes que bloqueiam sockets precisam permitir servidor e cliente HTTP locais para os testes de API e navegador.

## Organização e materiais

| Caminho | Conteúdo |
|---|---|
| `src/estoquepro/domain.py` | Validação, autenticação e transações SQLite |
| `src/estoquepro/server.py` | API HTTP, sessões, CSRF e arquivos estáticos |
| `src/estoquepro/static/` | Interface HTML, CSS e JavaScript |
| `database/schema.sql` | Esquema versionado inicial, chaves e restrições |
| `tests/` | Testes automatizados de domínio, API e navegador |
| [docs/planejamento.md](docs/planejamento.md) | Problema, escopo, arquitetura e cronograma |
| [docs/requisitos.md](docs/requisitos.md) | RF, RNF, regras e aceitação |
| [docs/casos-de-uso.md](docs/casos-de-uso.md) | Fluxos principais, alternativos e exceções |
| [docs/diagramas](docs/diagramas) | Fontes UML/DER e visualização local |
| [docs/operacao.md](docs/operacao.md) | Instalação, API, backup e recuperação |
| [docs/documentacao-academica.md](docs/documentacao-academica.md) | Documento acadêmico provisório e conformidade |
| [docs/testes/resultado.md](docs/testes/resultado.md) | Evidências e limites da validação |
| [backlog/backlog.csv](backlog/backlog.csv) | Backlog importável |
| [apresentacao/apresentacao.md](apresentacao/apresentacao.md) | Slides em Markdown e roteiro |

## Segurança e limites de operação

As senhas usam PBKDF2-SHA256 com salt aleatório e 260.000 iterações. A API exige sessão e protege alterações com token CSRF. Consultas SQL são parametrizadas; preços são armazenados em centavos inteiros. O CSV neutraliza fórmulas de planilha.

O servidor HTTP incluído é destinado a desenvolvimento e demonstração acadêmica local. Para operação pública, são necessários servidor/proxy de produção com HTTPS, controle de acesso, gestão de usuários e política operacional. `ESTOQUEPRO_SECURE_COOKIE=1` habilita o atributo Secure quando servido por HTTPS. Sessões ficam na memória e são invalidadas ao reiniciar. Não exponha credenciais demo à rede.

## Pendências acadêmicas

O **PDF da especificação**, o **template oficial**, os **integrantes e suas responsabilidades** e a **data sorteada da apresentação** não foram fornecidos. A documentação é provisória e a conformidade com o PDF não pode ser declarada. As datas do cronograma vêm exclusivamente do texto enviado. Não houve push, publicação nem submissão acadêmica.
