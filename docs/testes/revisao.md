# Revisão de código, organização e testes — 04/11/2026

## Resultado final

**77 testes automatizados aprovados**, sem falhas/erros/ignorados na execução final:

| Suíte | Resultado |
|---|---|
| Django/PostgreSQL + Chromium | 57 aprovados; 90,391 s na última execução instrumentada |
| Compatibilidade SQLite | 17 aprovados |
| Helpers de instalação | 3 aprovados |

O tempo incluiu instrumentação e outros checks locais; não é benchmark de desempenho. A suíte Django usa PostgreSQL 17 de teste separado. Chromium executou cadastro/login, primeiro produto, entradas/saídas, relatórios, preços, navegação móvel, privilégios do Criador e o menu de ações com ajuste de alerta. Os arquivos de dados reais não são usados nos testes de domínio/interface.

Cobertura de **87,84% considerando linhas e ramos** sobre `inventory/` e `config/`: 1.533/1.693 linhas e 302/396 ramos exercitados. Migrações, testes e WSGI estão fora dessa métrica. As migrações foram verificadas por aplicação em bancos novos e na restauração integral. A métrica não representa todos os caminhos possíveis e não substitui revisão independente.

## Correções comprovadas

1. Membro não acessa fluxo de caixa/análise financeira, mas continua podendo exportar posição de estoque autorizada.
2. IDs inválidos, texto SQL em filtros, números fora do alcance e cursor de notificação enorme recebem resposta controlada em vez de erro interno.
3. Conta desativada não executa serviços por meio de um objeto de acesso antigo.
4. Saldo máximo é validado antes da escrita; falha não modifica custo, saldo ou histórico parcialmente.
5. Motivo livre não define se um movimento é venda/transferência/inventário. A migração 0006 introduz finalidade estruturada e classifica os eventos identificáveis anteriores.
6. Lotes com códigos longos não colidem ao confirmar uma transferência.
7. Master de negócio filho não desativa renovação da assinatura de origem quando é apenas Membro na origem; downgrade da origem não permite escrita pela empresa filha para contornar limites.
8. Recebimento de pedido e inclusão de linha concorrentes releem o status sob bloqueio. Um pedido recebido não recebe linha sem entrada correspondente.
9. Worker usa lease por tentativa: uma execução atrasada não substitui o resultado de uma tentativa nova; timeouts/falhas têm limite de três tentativas.
10. Dashboard/listagem/análise agregam saldos/consumo, evitando uma consulta por produto. Comparação com 100 produtos adicionais verifica crescimento de consultas de no máximo três, sem alegar SLA de carga.
11. HTML malicioso em nome é escapado; SVG não é aceito como logo; arquivos privados não podem ser baixados por outro negócio ou por caminho que escape do diretório privado.
12. Criador é único, senha é solicitada sem eco e nunca impressa; a provisão para outro dono é recusada. O último Master **ativo** não pode ser removido, mesmo que haja Masters inativos.

## Melhorias solicitadas durante a revisão

- Ações de produto com botão principal Registrar entrada e popover Mais, sem ser cortado pela rolagem da tabela.
- Limite de reposição editável por produto em atalho próprio, sem alterar saldo. 1 avisa com uma unidade ou menos; 0 somente quando zera. Membros não alteram esse limite.
- Admin/Master podem adicionar membros, respeitando quota. Admin só cria Membro; Master/Criador atribui cargos de gestão. Tentativa de forjar cargo no POST é recusada.
- Campo e página explicam o significado de alerta e as permissões da equipe.

## Organização e remoções

Estrutura detalhada em [ESTRUTURA.md](../ESTRUTURA.md). Views foram separadas por área, testes agrupados e imports wildcard eliminados. CSS/JS/Python foram formatados e importações não utilizadas removidas. Estáticos atuais estão em `static/`, catálogo em `inventory/catalog.py` e a compatibilidade de importação em `legacy/`.

Foram removidos o servidor HTTP SQLite e a interface antiga, os testes HTTP/browser substituídos e um README duplicado obsoleto. Não foram apagados bancos, backups, contas, credenciais ou volumes. Caches/relatórios ficam ignorados. O histórico Git e os materiais acadêmicos preservam as versões anteriores.

## Checks adicionais executados

- Ruff: lint e formatação aprovados; sintaxe JavaScript aprovada com Node.
- `pip check`: nenhum requisito quebrado.
- `pip-audit`: **14 dependências de produção, zero vulnerabilidades conhecidas retornadas** na consulta. Não equivale a ausência de vulnerabilidades desconhecidas.
- Bandit: nenhum achado alto/médio. Há **16 apontamentos baixos** ligados ao uso de `subprocess` nos scripts locais. Revisão manual confirmou listas de argumentos, sem `shell=True` ou interpolação de comandos; scripts são ferramentas do operador, não endpoints públicos. Os alertas foram mantidos no relatório bruto, sem ocultação global.
- `check`, `makemigrations --check --dry-run` e `collectstatic --clear`: aprovados. Estáticos antigos gerados foram limpos e recriados sem tocar nos dados privados.
- `check --deploy` com DEBUG desligado: somente W021, referente a HSTS preload não ativado. Domínio/HTTPS público ainda não foram definidos; não se ativou preload apenas para silenciar o aviso.
- Dockerfile: build real aprovado, com CA confiável montada e verificação TLS preservada. Imagem final com usuário UID 10001, sem dados/configurações pessoais ou backups.
- Smoke da imagem com PostgreSQL temporário: migrações, Gunicorn, resposta de login 200, cookies seguros, redirecionamento para HTTPS, coleta de estáticos e execução do worker aprovados. Containers, volumes anônimos e rede de teste foram removidos ao terminar.
- Docker Compose: configuração validada por `docker compose config --quiet`, sem imprimir segredos. Não foi feita publicação do Compose em hospedagem pública.
- Backup integral `pg_dump -Fc` restaurado em banco temporário: equivalência de **1 Criador, 4 produtos, 3 eventos e 94 unidades**. O banco atual foi preservado; banco de restauração removido após o check.
- Links locais da documentação conferidos. Novas capturas e relatórios brutos em `data/quality/`, ignorado pelo Git.

## Reproduzir

Na raiz, com PostgreSQL disponível:

```sh
python scripts/dev.py migrate
python scripts/dev.py test inventory --noinput
python -m unittest discover -s tests -v
python -m unittest discover -s legacy/tests -v
```

A suíte de navegador requer `requirements-browser.txt` e Chromium; sem a dependência, o resultado deve ser registrado como ignorado, não como aprovado. Ferramentas de qualidade estão em `requirements-dev.txt`. Para conferir a imagem após build: `python scripts/check_container.py --image estoquepro:review`.

## Limitações e itens não executados

Não existe teste exaustivo de todos os estados possíveis. Esta revisão foi executada em Linux/Python 3.12/PostgreSQL 17/Chromium, sem homologação local em CachyOS/Python 3.14, Firefox, Safari ou Windows. Sem pentest externo, carga de produção, auditoria fiscal da NF-e ou testes de integrações reais Google/SMTP/WhatsApp/pagamentos. Essas integrações continuam desativadas/pendentes; não foram simuladas como entregues. Não houve implantação pública, alteração de nome do projeto ou submissão acadêmica.
