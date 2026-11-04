# EstoquePro

Gestão de estoque com **Django, PostgreSQL e interface HTML/CSS/JavaScript**. Nome mantido para a apresentação acadêmica. O suporte à importação do SQLite está preservado em `legacy/`; o servidor e a interface obsoletos foram removidos.

## Executar localmente (bash, fish ou PowerShell)

Requisitos: Python 3.12+, Docker disponível e navegador. Na pasta do repositório:

```text
python -m venv .venv
```

Linux/fish/bash:

```sh
.venv/bin/python -m pip install -r requirements.txt
python scripts/dev.py setup
python scripts/dev.py import_legacy data/estoquepro.sqlite3 --name "EstoquePro apresentação"
python scripts/dev.py provision_creator --username Lxzinxs
python scripts/dev.py runserver 127.0.0.1:8000 --noreload
```

Windows PowerShell (Docker Desktop em execução):

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
python scripts/dev.py setup
python scripts/dev.py import_legacy data/estoquepro.sqlite3 --name "EstoquePro apresentação"
python scripts/dev.py provision_creator --username Lxzinxs
python scripts/dev.py runserver 127.0.0.1:8000 --noreload
```

`import_legacy` é opcional: use apenas se o SQLite antigo existir. Não apaga o arquivo original e não duplica uma importação idêntica. Havendo nome de usuário conflitante, interrompe sem sobrescrever dados. Em banco novo, você pode criar seu negócio pela página Cadastro. O comando `provision_creator` solicita senha e confirmação sem eco; não passe a senha em argumentos nem a grave no Git. Existe apenas um cargo Criador. Em outra máquina, provisione novamente o seu usuário; credenciais/bancos locais não são enviados ao GitHub.

O servidor é acessado pela porta 8000 no navegador local. Encerre o servidor antigo antes de usar a mesma porta. Em onboarding na nuvem, validação e acesso são internos; não há publicação de prévia automática.

Em outro terminal, execute o worker para relatórios, exportações de backup e agendamentos:

```sh
python scripts/dev.py runworker
```

Para processar uma única tarefa: `python scripts/dev.py runworker --once`.

O helper guarda configuração de desenvolvimento e senha aleatória do PostgreSQL em `data/`, ignorado pelo Git. Não compartilhe esses arquivos. Não remova o volume do PostgreSQL ou o diretório `data` para resolver problemas de login. O identificador interno do container local é `nerythstock-postgres`, preservado para não perder o volume criado durante a migração; a marca exibida é EstoquePro.

## Recursos da nova versão

- Organizações isoladas, equipe com Membro/Admin/Master e cargo global exclusivo Criador.
- Login, logout, troca e recuperação de senha, CSRF, limitação de tentativas e auditoria.
- Produtos, categorias, fornecedores, filiais, locais/pontos de atendimento e códigos de barras.
- Entradas/saídas, custo médio ponderado, lotes/validade FEFO e movimentação em lote atômica.
- Pedidos de compra com recebimento idempotente; transferências com confirmação.
- Contas a pagar/receber, baixas parciais, caixa por período, cotações e inventário cego.
- Cobertura, Curva ABC, sugestões por regras locais e pedido sugerido com compartilhamento manual por WhatsApp.
- Histórico paginado, CSV/Excel/PDF, etiquetas Code128, logo em PDFs e tarefas em segundo plano.
- Básico de um mês/1 conta/50 produtos; Completo sem quota comercial, com vigência definida pelo Criador enquanto não há gateway.

Os detalhes, critérios, limites e pendências estão em [MIGRACAO_DJANGO.md](docs/MIGRACAO_DJANGO.md). **O produto ainda não está homologado para venda.** Google Drive, gateway, suporte e notificações externas não estão ativos; transferências usam atualização periódica, não sincronização instantânea. Domínio, e-mail e WhatsApp de suporte foram deixados desativados a pedido do usuário.

## Testes

```sh
python scripts/dev.py test inventory.tests.test_core inventory.tests.test_review --noinput
```

Testes usam PostgreSQL de teste separado e verificam isolamento, permissões, Criador exclusivo, concorrência, FEFO, custos, pedidos, financeiro, NF-e, importação legada, filas e exportações. A conta local do PostgreSQL de desenvolvimento permite criar banco de teste; a conta de produção deve ter privilégios reduzidos e uma conta separada para migrações/testes.

Navegador opcional:

```sh
.venv/bin/python -m pip install -r requirements-browser.txt
python scripts/dev.py test inventory.tests.test_browser --noinput
```

No Windows, use `.venv\Scripts\python.exe` para instalar. Defina `CHROMIUM_PATH` se o Chromium não estiver em `/usr/bin/chromium`, ou adapte o teste para o navegador instalado pelo Playwright. Capturas em `data/quality/screenshots/` (não versionadas). Os exemplos de apresentação permanecem em `docs/prototipos/`.

## Produção e configuração

`config/settings.py` exige `DJANGO_SECRET_KEY` fora do modo de desenvolvimento. Configure `PG*`, `DJANGO_ALLOWED_HOSTS` e origens CSRF explícitas. Use Gunicorn atrás de proxy HTTPS e sirva `collectstatic` pelo proxy; cookies seguros e redirecionamento HTTPS são padrão fora de DEBUG. Não exponha `runserver` nem ative DEBUG publicamente. `scripts/dev.py` é apenas para desenvolvimento e apresentação.

`Dockerfile`, `compose.yaml` e `.env.example` preparam os serviços web/worker/PostgreSQL; precisam de segredos e proxy TLS antes de implantação. O Compose não cria senhas ou habilita SMTP automaticamente. `python manage.py migrate`, `collectstatic --noinput` e provisão do Criador são etapas explícitas da implantação. Build com proxy da nuvem deve montar a CA confiável via `docker build --secret id=proxy_ca,src=/etc/ssl/certs/ca-certificates.crt .`; verifique o bundle configurado no ambiente. Não desative TLS.

No ambiente local, `python scripts/backup_database.py` cria backup integral privado; restauração foi validada em banco separado (ver [evidências](docs/testes/django.md)). Em produção, faça backup integral com `pg_dump -Fc` e cópia segura de arquivos/configuração. A tarefa de backup da interface é exportação consistente dos dados do negócio sem senhas: não substitui backup completo de recuperação de desastre.

## Documentação acadêmica

Materiais anteriores estão em `docs/`, `backlog/` e `apresentacao/`; os documentos legados descrevem a versão SQLite e devem ser lidos junto ao adendo [MIGRACAO_DJANGO.md](docs/MIGRACAO_DJANGO.md). O PDF e o template oficial ainda não foram fornecidos. A entrega acadêmica final continua provisória e não foi submetida automaticamente.

### CachyOS / Arch Linux: Docker ausente

Se setup informar que não encontrou `docker`, a instalação Python não precisa ser refeita. No CachyOS:

```sh
sudo pacman -S docker
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"
```

Saia da sessão do KDE e entre novamente para aplicar o grupo. Em um terminal novo, confirme `docker info` e só então execute `python scripts/dev.py setup`. Se setup falhar, não prossiga para `provision_creator`: o banco ainda não está pronto. Não execute o projeto inteiro com sudo e não apague `data/` ou volumes.

### Interface e primeiro produto

A navegação está agrupada e os formulários mostram orientações. Para cadastrar o primeiro produto, informe código e nome, mantendo os valores padrão se necessário: a categoria Geral é automática e fornecedor é opcional. Depois use **Registrar entrada** para informar quantidade e custo de compra. Categorias/fornecedores também podem ser criados no próprio formulário em **Organização e fornecedor**. O Criador vê **Completo — acesso permanente do Criador** em Assinatura e não precisa contratar um plano.


## Organização e revisão

A estrutura atual está em [docs/ESTRUTURA.md](docs/ESTRUTURA.md). `inventory/views/` separa os endpoints por área; `inventory/tests/` organiza os testes; `static/` contém os arquivos visuais atuais; `legacy/` mantém apenas compatibilidade de migração. O antigo servidor HTTP e sua interface foram removidos. Não há necessidade de mudar o caminho do banco para atualizar a aplicação.

Depois de atualizar, encerre o servidor/worker antigos, execute **`python scripts/dev.py migrate`** e reinicie-os. A migração 0006 adiciona classificação de movimentações e proteção de execução do worker, sem apagar produtos, usuários ou históricos.

Testes sem Django e de compatibilidade:

```sh
python -m unittest discover -s tests -v
python -m unittest discover -s legacy/tests -v
```

Ferramentas opcionais: instale `requirements-dev.txt` no ambiente virtual. O projeto inclui configuração de Ruff e cobertura em `pyproject.toml`. Resultados gerados ficam em `data/quality/` e não entram no Git. A revisão e seus limites estão em [docs/testes/revisao.md](docs/testes/revisao.md).

Na lista de Produtos, **Registrar entrada** é a ação principal; **Mais** reúne edição, alerta, histórico e arquivamento. Em **Alerta quando**, clique para ajustar o limite: 1 avisa com uma unidade ou menos; 0 avisa somente ao zerar. Essa configuração não adiciona ou remove estoque.

**Adicionar membro** está disponível para Admin e Master (respeitando a quota do plano). Admin cria Membros; apenas Master ou Criador atribui cargos de gestão e altera cargos existentes. O último Master não pode ser removido.

Se o Docker funciona, mas o script informa falha no PostgreSQL, execute:

```sh
python scripts/dev.py doctor
docker ps --filter name=nerythstock-postgres
docker port nerythstock-postgres
```

O diagnóstico testa a autenticação com a mesma configuração usada pela aplicação,
sem mostrar senhas. `pg_isready` indica disponibilidade, mas não valida a senha.
Um volume PostgreSQL existente conserva as credenciais originais mesmo se o
arquivo de configuração for recriado. Não apague `data/` nem o volume para corrigir
uma falha de conexão; não publique arquivos `.env`.

Se `doctor` confirmar **autenticação recusada** no container local dedicado, use:

```sh
python scripts/dev.py repair-db-password
python scripts/dev.py setup
```

Esse comando explícito sincroniza a senha do usuário PostgreSQL existente com
`data/django-local.env`, pela conexão interna do container. Preserva tabelas,
volumes e usuários do EstoquePro (inclusive suas senhas de login). Restringe a
recuperação ao container `nerythstock-postgres` publicado em `127.0.0.1:55432`;
não serve para bancos remotos. Outros clientes que usem esse mesmo usuário do
banco precisarão da senha atualizada. O comando não mostra a senha e verifica
a autenticação ao terminar. Não recria banco nem usuário ausente.
