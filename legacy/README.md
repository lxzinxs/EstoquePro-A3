# Compatibilidade com a versão SQLite

Este diretório contém apenas o domínio e o esquema históricos necessários para os testes e para comprovar a importação. O servidor HTTP, a interface e os testes HTTP da versão antiga foram removidos porque foram substituídos por Django. O código completo anterior continua no histórico Git.

Não inicie uma aplicação por este diretório. Use `python scripts/dev.py setup` e os comandos do README principal. Bancos SQLite existentes em `data/` não foram movidos ou apagados.

Teste de compatibilidade (na raiz):

```sh
python -m unittest discover -s legacy/tests -v
```

O comando de migração principal continua sendo `python scripts/dev.py import_legacy data/estoquepro.sqlite3`.
