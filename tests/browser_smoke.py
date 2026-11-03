"""Teste de interface opcional. Requer Playwright e Chromium instalados."""
import os
import sys
import tempfile
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from estoquepro.domain import Inventory, ROOT
from estoquepro.server import Application
from playwright.sync_api import sync_playwright, expect


def run():
    with tempfile.TemporaryDirectory() as temporary:
        db = Inventory(Path(temporary) / 'browser.sqlite3')
        db.initialize('SenhaNavegador123', demo=True)
        server = Application(('127.0.0.1', 0), db)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with sync_playwright() as playwright:
                executable = os.environ.get('CHROMIUM_PATH')
                browser = playwright.chromium.launch(**({'executable_path': executable} if executable else {}))
                page = browser.new_page(viewport={'width': 1440, 'height': 1000}, locale='pt-BR', timezone_id='America/Sao_Paulo')
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(f'http://127.0.0.1:{server.server_port}')
                page.get_by_role('tab', name='Cadastro', exact=True).click()
                registration = page.locator('#register-form')
                registration.get_by_label('Usuário', exact=True).fill('conta.navegador')
                registration.get_by_label('Senha', exact=True).fill('NovaSenha123')
                registration.get_by_label('Confirmar senha', exact=True).fill('OutraSenha123')
                registration.get_by_role('button', name='Criar conta e entrar').click()
                expect(page.locator('#register-error')).to_have_text('As senhas não coincidem.')
                registration.get_by_label('Confirmar senha', exact=True).fill('NovaSenha123')
                page.screenshot(path=str(ROOT / 'docs/prototipos/cadastro-desktop.png'), full_page=True)
                registration.get_by_role('button', name='Criar conta e entrar').click()
                expect(page.get_by_role('heading', name='Seu catálogo')).to_be_visible()
                expect(page.locator('#account-name')).to_have_text('conta.navegador')
                page.get_by_role('button', name='Sair', exact=True).click()
                expect(page.get_by_role('button', name='Entrar no sistema')).to_be_visible()
                page.locator('#login-form').get_by_label('Usuário', exact=True).fill('admin')
                page.locator('#login-form').get_by_label('Senha', exact=True).fill('SenhaNavegador123')
                page.get_by_role('button', name='Entrar no sistema').click()
                expect(page.get_by_role('heading', name='Seu catálogo')).to_be_visible()
                page.screenshot(path=str(ROOT / 'docs/prototipos/dashboard-desktop.png'), full_page=True)
                page.set_viewport_size({'width': 390, 'height': 844})
                page.screenshot(path=str(ROOT / 'docs/prototipos/dashboard-mobile.png'), full_page=True)
                assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), 'Overflow horizontal no celular'
                page.set_viewport_size({'width': 1440, 'height': 1000})
                page.get_by_role('link', name='Categorias', exact=False).click()
                page.get_by_role('button', name='Nova categoria').click()
                dialog = page.get_by_role('dialog')
                dialog.get_by_label('Nome', exact=True).fill('Categoria navegador')
                dialog.get_by_role('button', name='Salvar').click()
                expect(page.get_by_role('heading', name='Categoria navegador', exact=True)).to_be_visible()
                page.get_by_role('link', name='Fornecedores', exact=False).click()
                page.get_by_role('button', name='Novo fornecedor').click()
                dialog.get_by_label('Nome', exact=True).fill('Fornecedor navegador')
                dialog.get_by_role('button', name='Salvar').click()
                expect(page.get_by_role('heading', name='Fornecedor navegador', exact=True)).to_be_visible()
                page.get_by_role('link', name='Produtos', exact=True).click()
                page.get_by_role('button', name='Novo produto').click()
                dialog.get_by_label('Nome do produto').fill('Produto navegador')
                dialog.get_by_label('Código / SKU').fill('WEB-001')
                dialog.get_by_label('Preço de referência').fill('25.50')
                dialog.get_by_label('Categoria', exact=True).select_option(label='Categoria navegador')
                dialog.get_by_label('Fornecedor', exact=True).select_option(label='Fornecedor navegador')
                dialog.get_by_label('Estoque mínimo').fill('2')
                dialog.get_by_role('button', name='Salvar').click()
                expect(page.get_by_role('button', name='Editar Produto navegador', exact=True)).to_be_visible()
                page.get_by_label('Buscar produtos').fill('WEB-001')
                expect(page.locator('tbody tr')).to_have_count(1)
                page.get_by_role('button', name='Editar Produto navegador', exact=True).click()
                dialog.get_by_label('Preço de referência').fill('26.90')
                dialog.get_by_role('button', name='Salvar').click()
                expect(dialog).not_to_be_visible()
                expect(page.get_by_role('button', name='Editar Produto navegador', exact=True)).to_be_visible()
                page.get_by_role('link', name='Movimentações', exact=False).click()
                page.get_by_role('button', name='Nova movimentação').click()
                dialog.get_by_label('Produto', exact=True).select_option(label='Produto navegador · WEB-001 · saldo 0')
                dialog.get_by_label('Quantidade').fill('5')
                dialog.get_by_label('Motivo').fill('Recebimento navegador')
                dialog.get_by_role('button', name='Salvar').click()
                expect(page.get_by_role('cell', name='Recebimento navegador', exact=True)).to_be_visible()
                page.get_by_role('button', name='Nova movimentação').click()
                dialog.get_by_label('Produto', exact=True).select_option(label='Produto navegador · WEB-001 · saldo 5')
                dialog.get_by_label('Tipo', exact=True).select_option('saida')
                dialog.get_by_label('Quantidade').fill('6')
                dialog.get_by_label('Motivo').fill('Saída inválida')
                dialog.get_by_role('button', name='Salvar').click()
                expect(page.locator('#modal-error')).to_have_text('Saldo insuficiente para esta saída.')
                dialog.get_by_label('Quantidade').fill('5')
                dialog.get_by_label('Motivo').fill('Saída navegador')
                dialog.get_by_role('button', name='Salvar').click()
                expect(page.get_by_role('cell', name='Saída navegador', exact=True)).to_be_visible()
                page.screenshot(path=str(ROOT / 'docs/prototipos/movimentacoes-desktop.png'), full_page=True)
                page.get_by_role('link', name='Produtos', exact=True).click()
                page.get_by_role('button', name='Arquivar Produto navegador', exact=True).click()
                dialog.get_by_role('button', name='Salvar').click()
                expect(dialog).not_to_be_visible()
                expect(page.get_by_role('button', name='Editar Produto navegador', exact=True)).to_have_count(0)
                page.get_by_role('link', name='Relatórios', exact=False).click()
                with page.expect_download() as download:
                    page.get_by_role('button', name='Baixar relatório CSV').click()
                assert download.value.suggested_filename == 'estoquepro.csv'
                page.reload()
                expect(page.get_by_role('button', name='Baixar relatório CSV')).to_be_visible()
                page.get_by_role('button', name='Sair', exact=True).click()
                expect(page.get_by_role('button', name='Entrar no sistema')).to_be_visible()
                assert not errors, errors
                browser.close()
                print('PASS: cadastro, confirmação de senha, sessão do novo usuário, login, dashboard, mobile, categoria, fornecedor, produto, edição, busca, entrada, saída inválida, saída válida, arquivo, CSV, sessão e logout; zero erros JavaScript.')
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == '__main__':
    run()
