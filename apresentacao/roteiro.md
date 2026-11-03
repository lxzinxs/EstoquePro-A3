# Roteiro de apresentação e demonstração

Duração sugerida: 8–10 minutos; ajustar ao tempo exigido no PDF. Responsáveis e ordem de fala devem ser preenchidos pela equipe real. Apresentação proposta para 18/11 ou 24/11/2026, conforme sorteio ainda não informado.

| Tempo sugerido | Conteúdo | Evidência |
|---|---|---|
| 0:00–1:00 | Identificação, problema, público e justificativa | Slides iniciais |
| 1:00–2:30 | Escopo, requisitos e regras | docs/requisitos.md |
| 2:30–4:00 | Arquitetura, classes, DER e transação | docs/diagramas/ |
| 4:00–7:00 | Demonstração real abaixo | Aplicação local |
| 7:00–8:30 | Testes, dificuldades e soluções | docs/testes/resultado.md |
| 8:30–10:00 | Limitações, conclusão e perguntas | Checklist acadêmico |

## Preparação

Em banco próprio de demonstração, iniciar `PYTHONPATH=src python -m estoquepro.server --demo --database data/apresentacao.sqlite3`. Se já houver dados, não apagar: escolher outro caminho novo para um ensaio independente. Testar entrada antes da apresentação; manter a senha demo restrita ao ambiente local. Abrir slides Markdown em ferramenta compatível; Marp é opcional, não foi usado para gerar PDF nesta entrega.

## Fluxo narrado

1. Entrar como admin. Mostrar quatro indicadores e alertas dos dados fictícios.
2. Criar categoria `Demonstração A3` e produto de código exclusivo, nome `Produto A3`, preço 10,50 e mínimo 3.
3. Registrar entrada de 5 com motivo `Recebimento para demonstração`. Mostrar saldo 5.
4. Tentar saída de 6. Mostrar erro sem fechar o formulário e explicar que saldo e histórico ficam preservados.
5. Corrigir para saída de 3, motivo `Consumo para demonstração`. Mostrar saldo 2, alerta e os dois registros no histórico.
6. Filtrar pelo código e por estoque baixo. Editar o nome/preço e explicar que o saldo só muda por movimentação.
7. Exportar CSV e conferir linha do produto. Não afirmar que o relatório representa custo contábil.
8. Opcional: retirar as 2 unidades restantes, arquivar e mostrar histórico preservado. Não é exclusão física.
9. Sair. Executar `python -m unittest discover -s tests -v` se o tempo permitir, distinguindo a suíte API do teste de navegador.

Se o navegador não estiver disponível no dia, usar capturas como apoio e declarar que a demonstração ao vivo não ocorreu. Não apresentar capturas como execução atual.

## Perguntas esperadas

- Por que SQLite? Adequado ao uso local com baixo volume e sem serviço separado.
- Como evitar estoque negativo concorrente? `BEGIN IMMEDIATE` serializa escritores antes de ler o saldo; há teste com duas saídas.
- Como corrigir erro humano? Nova movimentação compensatória com motivo; não reescrever histórico.
- Como recuperar dados? Backup consistente e restauração em caminho novo, descritos no manual.
- O que falta para produção? Gestão de usuários, recuperação de senha, operação HTTPS, servidor de produção e validações operacionais adicionais.
