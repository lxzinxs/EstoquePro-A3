# Manual técnico e de operação

## Instalação e inicialização

Usar o checkout existente; as tarefas de nuvem já são isoladas, portanto não criar worktree para configurar. Na raiz do repositório, executar os comandos do README. Python 3.12+ é o único requisito obrigatório. A inicialização cria tabelas e índices sem apagar dados. Não há compilação nem download de dependências em execução.

Parâmetros: `--host` (padrão `127.0.0.1`), `--port` (8000), `--database` (caminho do SQLite) e `--demo`. O modo demo recusa outro host. `--reset-demo-admin`, combinado com `--demo`, redefine explicitamente o administrador para a credencial de demonstração sem alterar o catálogo ou o histórico. Ao iniciar normalmente com `--demo` e sem senha de ambiente, somente a antiga senha padrão `EstoquePro@2026` é migrada automaticamente para `admin123`; outras senhas são preservadas. Para verificar prontidão, solicitar a página inicial e efetuar login seguido de consulta a `/api/dashboard`; apenas uma porta aberta não comprova funcionamento.

Configuração opcional: `ESTOQUEPRO_ADMIN_PASSWORD` define a senha inicial apenas de um banco novo; `ESTOQUEPRO_SECURE_COOKIE=1` exige transporte HTTPS do navegador para o cookie. Valores de senha devem permanecer fora dos arquivos do projeto. `PYTHONPATH=src` é necessário ao executar pelo módulo na raiz. Sessões não sobrevivem a reinícios.

## Guia do usuário

1. Entrar com o usuário configurado ou selecionar Cadastro para criar conta local. Usar usuário de 3–32 letras ASCII/números/ponto/hífen/sublinhado, senha de 8–256 caracteres e confirmação idêntica. O nome é salvo em minúsculas; contas compartilham o mesmo estoque e permissões.
2. Em Categorias, criar ao menos uma categoria. Fornecedores são opcionais e só armazenam nome.
3. Em Produtos, criar código, nome, categoria, fornecedor opcional, preço de referência e mínimo. O saldo inicial é zero.
4. Em Movimentações, selecionar produto, entrada ou saída, quantidade inteira positiva e motivo. Conferir antes de salvar: o histórico não é editável.
5. Consultar painel ou filtrar Produtos por texto, categoria e estoque baixo. Saldo igual ao mínimo já dispara atenção.
6. Para corrigir uma movimentação, fazer uma nova movimentação compensatória e explicar o motivo.
7. Arquivar somente quando o saldo estiver zero. O código continua reservado e o histórico permanece.
8. Em Relatórios, baixar CSV para análise em planilha. O relatório contém todos os produtos ativos, independentemente dos filtros da tela de produtos.
9. Sair para invalidar a sessão.

## API

JSON em UTF-8, `Content-Type: application/json` para corpos, máximo 16 KB. Cookie `session` HttpOnly/SameSite=Strict; obter `csrf` no login ou consulta da sessão e enviá-lo em `X-CSRF-Token` nas alterações. Não há CORS habilitado.

| Método | Caminho | Corpo / resultado |
|---|---|---|
| POST | `/api/login` | `{username,password}` → `{user,csrf}` e cookie |
| POST | `/api/register` | `{username,password,confirm_password}` → 201, `{user,csrf}` e cookie; apenas servidor em loopback |
| GET | `/api/session` | Usuário e token CSRF |
| POST | `/api/logout` | Invalida sessão |
| GET | `/api/dashboard` | products, units, value_cents, low |
| GET/POST | `/api/categories` | Lista / `{name}` → id |
| GET/POST | `/api/suppliers` | Lista / `{name}` → id |
| GET | `/api/products?q=&category=&low=1` | Produtos ativos filtrados |
| POST | `/api/products` | sku, name, category_id, supplier_id opcional, price em reais, minimum |
| PUT | `/api/products/{id}` | Mesmos metadados; não altera saldo |
| DELETE | `/api/products/{id}` | Arquiva com saldo zero |
| GET | `/api/movements` | Últimos 200 eventos, mais recentes primeiro |
| POST | `/api/movements` | product_id, kind (`entrada`/`saida`), quantity, note |
| GET | `/api/report.csv` | CSV com BOM UTF-8 e separador `;` |

Erros: 400 validação; 401 sem autenticação; 403 CSRF/origem; 404 rota desconhecida; 409 duplicidade/integridade; 429 limite de tentativas; 503 banco indisponível; 500 falha interna. Mensagens não expõem SQL ou credenciais. Dez tentativas de login por minuto/IP, contando as bem-sucedidas; limite e sessões são locais ao processo.

## Banco e dicionário

Modelo conceitual: categoria classifica produtos, fornecedor abastece produtos, usuário registra movimentações que afetam um produto. Modelo lógico/DER em `diagramas/der.mmd`; implementação em `database/schema.sql`.

| Tabela | Campos e restrições principais |
|---|---|
| users | id PK INTEGER; username TEXT UNIQUE NOT NULL; password_hash TEXT NOT NULL (salt:digest); created_at TEXT UTC |
| categories | id PK INTEGER; name TEXT UNIQUE NOCASE, 1–80 caracteres |
| suppliers | id PK INTEGER; name TEXT UNIQUE NOCASE, 1–80 caracteres |
| products | id PK INTEGER; sku TEXT UNIQUE NOCASE; name TEXT; category_id FK obrigatória; supplier_id FK opcional; price_cents INTEGER ≥0; minimum INTEGER ≥0; quantity INTEGER ≥0; active INTEGER 0/1; created_at TEXT UTC |
| movements | id PK INTEGER; product_id FK; user_id FK; kind TEXT entrada/saida; quantity INTEGER >0; note TEXT; balance_after INTEGER ≥0; created_at TEXT UTC |

Dados em terceira forma normal para entidades cadastrais; categoria e fornecedor não são repetidos nos produtos. `quantity` e `balance_after` são redundâncias deliberadas para saldo corrente e auditoria, mantidas atomicamente. Os registros não guardam preço histórico, por isso o relatório não representa custo passado. Datas são UTC no SQLite e exibidas no fuso do navegador.

## Backup e restauração

Use a API de backup SQLite para obter uma cópia consistente, inclusive com WAL. Na raiz, com o diretório `data` já inicializado:

```bash
python - <<'PY'
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
folder = Path('data/backups')
folder.mkdir(parents=True, exist_ok=True)
target = folder / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.sqlite3')
with sqlite3.connect('data/estoquepro.sqlite3') as source, sqlite3.connect(target) as dest:
    source.backup(dest)
    assert dest.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
print('Backup criado:', target)
PY
```

Para restaurar, parar o servidor, preservar o diretório `data` atual completo em local seguro, validar a cópia com `PRAGMA integrity_check`, escolher um caminho novo e iniciar com `--database caminho/backup.sqlite3` sem `--demo`. Não sobrescrever banco em uso ou ignorar arquivos WAL/SHM. Fazer login com a senha existente naquela cópia. Backups contêm hashes e dados do negócio e precisam de controle de acesso; ficam ignorados no Git. Recomenda-se rotina diária e teste periódico de restauração pelo responsável; o aplicativo não agenda backups.

## Diagnóstico

- Porta ocupada: escolher outra com `--port`.
- Sem categoria: cadastrar antes de criar produto.
- Código duplicado: escolher código novo; códigos arquivados permanecem reservados.
- Saldo insuficiente: revisar quantidade ou registrar uma entrada legítima; não editar banco manualmente.
- Sessão expirada: entrar novamente. O prazo é absoluto de oito horas.
- SQLite indisponível: verificar espaço e permissões do diretório, encerrar ferramentas que mantenham escrita longa e tentar novamente.
- Sockets bloqueados pelo executor: executar os testes com a permissão de rede local disponibilizada pela plataforma; não desativar autenticação ou CSRF.
- Sem senha de um banco já criado: não há recuperação implementada. Preservar dados e tratar recuperação administrativa como tarefa separada.
