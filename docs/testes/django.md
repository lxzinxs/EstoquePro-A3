# Validação da migração Django/PostgreSQL — 04/11/2026

## Resultado final executado

`python scripts/dev.py test inventory --noinput`: **27 testes aprovados**, zero falhas, erros ou ignorados, em 31,672 s nesta máquina. Backend do teste: PostgreSQL 17 real, em banco separado `test_nerythstock`. A suíte inclui o teste de navegador; não usa SQLite como substituto.

Cobertura por cenário: cadastro cria negócio isolado; referência a categoria/produto de outro negócio é recusada; arquivos privados não atravessam negócios; Membro não edita catálogo/auditoria/equipe; último Master não pode ser removido; Criador único recebe acesso global e ignora prazo/plano; Básico expira por mês de calendário sem bloquear consulta/exportação; quotas básicas; custo médio; FEFO ignora vencidos; rollback integral do lote; duas saídas concorrentes não deixam saldo negativo; recebimento de pedido idempotente; confirmação de transferência sem dupla entrada; pagamentos parciais sem exceder saldo; cotações limitadas; fechamento de contagem idempotente; XLSX/PDF reais e CSV seguro; XML sem entidades externas e NF-e duplicada recusada; worker gera arquivos privados e scheduler não duplica vencimento; CSRF; recuperação de senha em memória; formulários/listas; assinatura herdada em negócio adicional; importação legada idempotente com atualização de hash; limitação de login; leitor de barras, etiquetas, pedido sugerido, desativação de renovação e erro de período.

## Navegador

Chromium + Playwright 1.62.0: login; criação de produto; entrada de 5; saída de 6 rejeitada; saída de 3 aceita; análise por período; dashboard desktop 1440 px; mobile 390 px sem overflow global; logout; zero exceções JavaScript. Capturas `django-desktop.png` e `django-mobile.png`.

O primeiro ensaio do navegador falhou porque o loop do Playwright foi iniciado antes da preparação ORM, acionando corretamente a proteção assíncrona do Django. A estrutura do teste foi corrigida para criar fixtures antes de iniciar o navegador; a proteção não foi desativada. Um teste de plano identificou falta de autorização no GET inicial da análise; o check foi movido para o início da view e a regressão passou.

## Execução nesta máquina

- Cinco migrações aplicadas e `makemigrations --check --dry-run`: sem mudanças pendentes.
- `manage.py check`: nenhum problema. `check --deploy`, com DEBUG desligado e chave efêmera forte, retornou apenas W021 (HSTS preload não ativado). Preload foi mantido desativado porque domínio/TLS público não foram definidos; não é homologação da hospedagem.
- Importação real do SQLite antigo: **4 produtos / 3 movimentações / 94 unidades** preservados; origem intacta. Custos históricos não existiam e não foram inventados.
- Usuário `Lxzinxs` provisionado como único Criador por prompt sem eco; sessão de autenticação nativa e acesso global/admin verificados sem imprimir senha/hash/token.
- Django iniciado em loopback, porta 8000; worker separado executou uma tarefa real de backup com status `done`.
- Backup integral PostgreSQL criado com `pg_dump -Fc` em `data/backups/`, privado e ignorado pelo Git. Restauração concluída em banco temporário isolado: **1 Criador / 4 produtos / 3 eventos**, sem sobrescrever o banco atual. O banco temporário foi removido depois da verificação.
- Compilação Python e sintaxe do JavaScript novo verificadas.

## Limites da evidência

Execução validada em Linux/Python 3.12/PostgreSQL 17/Chromium; Windows e Docker Compose da aplicação não foram executados. Sem teste de carga, auditoria externa, homologação fiscal ou HTTPS público. SMTP, domínio, suporte e WhatsApp externo desativados por solicitação. Google Drive e gateway de pagamento não implementados; sincronização usa polling de 15 s. Ver lista completa de pendências em `docs/MIGRACAO_DJANGO.md`.

## Diagnóstico de instalação no CachyOS

Três testes unitários do helper (`python -m unittest discover -s tests -p test_runtime.py -v`) aprovados: CLI Docker ausente, permissão negada e preservação do contexto Docker Desktop fora do executor gerenciado. Setup agora verifica o daemon antes de tentar criar o banco; os comandos de aplicação verificam conectividade PostgreSQL antes de emitir traceback por banco indisponível. A instalação de pacotes na máquina CachyOS do usuário depende de execução local pelo usuário.
