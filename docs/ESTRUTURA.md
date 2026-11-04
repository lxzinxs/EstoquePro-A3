# Organização do repositório

| Pasta/arquivo | Responsabilidade |
|---|---|
| `config/` | Configuração Django, URLs e WSGI |
| `inventory/models.py` | Modelo de dados e restrições |
| `inventory/services.py` | Regras de negócio, autorização e transações |
| `inventory/views/` | Endpoints separados em contas, organizações, registros, estoque, financeiro e tarefas |
| `inventory/forms.py` | Campos, validação e escopo dos formulários |
| `inventory/jobs.py` | Scheduler, leases do worker e geração privada de arquivos |
| `inventory/reports.py` | CSV, Excel e PDF |
| `inventory/integrations.py` | Importação local de XML NF-e |
| `inventory/catalog.py` | Dados dos planos |
| `inventory/migrations/` | Evolução versionada do banco; não apagar migrações aplicadas |
| `inventory/tests/` | Testes de domínio/HTTP, regressão da revisão e navegador |
| `templates/` | Telas Django |
| `static/` | CSS e JavaScript atuais; não contém interface antiga |
| `scripts/` | Preparação local, backup integral e teste isolado de container |
| `tests/unit/` | Testes dos helpers sem Django/PostgreSQL |
| `legacy/` | Apenas domínio/esquema/testes necessários à compatibilidade SQLite |
| `docs/`, `apresentacao/`, `backlog/` | Documentação, materiais acadêmicos e planejamento |
| `data/` | Bancos, arquivos privados, credenciais locais, backups e resultados de testes; ignorado no Git |

## Limpeza realizada

O servidor HTTP SQLite, o HTML/JavaScript daquela interface, seus testes HTTP/browser substituídos e o README duplicado com instruções obsoletas foram removidos. O histórico Git preserva as versões anteriores. O domínio e esquema SQLite necessários para testar a migração foram mantidos em `legacy/`.

Os estáticos gerados foram recriados por `collectstatic --clear`, sem tocar em bancos ou arquivos privados. Cópias de dados, senhas e volumes não foram removidos. O nome interno antigo do container PostgreSQL foi preservado para não comprometer instalações existentes.

Execuções automatizadas gravam capturas e relatórios em `data/quality/`, evitando alterar as imagens da apresentação em cada teste. As imagens históricas em `docs/prototipos/` permanecem disponíveis como materiais acadêmicos.
