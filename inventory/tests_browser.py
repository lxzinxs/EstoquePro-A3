"""Teste opcional de interface: requirements-browser.txt + Chromium do sistema."""
import os
from pathlib import Path
from decimal import Decimal
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import *
from .services import month_after

class BrowserTests(StaticLiveServerTestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            import unittest
            raise unittest.SkipTest('Instale requirements-browser.txt para executar testes de navegador.')
        super().setUpClass()
    def test_django_full_workflow_and_mobile(self):
        from playwright.sync_api import expect
        user=get_user_model().objects.create_user('browser.master','browser@example.test','BrowserOnly!12345')
        org=Organization.objects.create(name='Negócio de teste',plan='complete',trial_ends_at=month_after(timezone.now()),paid_until=month_after(timezone.now(),12))
        Membership.objects.create(organization=org,user=user,role='master')
        company=Company.objects.create(organization=org,name='Principal')
        location=Location.objects.create(organization=org,company=company,name='Estoque')
        category=Category.objects.create(organization=org,name='Escritório')
        from playwright.sync_api import sync_playwright
        playwright=sync_playwright().start()
        self.addCleanup(playwright.stop)
        browser=playwright.chromium.launch(executable_path=os.getenv('CHROMIUM_PATH','/usr/bin/chromium'))
        self.addCleanup(browser.close)
        page=browser.new_page(viewport={'width':1440,'height':1000},locale='pt-BR',timezone_id='America/Sao_Paulo')
        errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
        page.goto(self.live_server_url+'/')
        page.locator('input[name=username]').fill('browser.master');page.locator('input[name=password]').fill('BrowserOnly!12345')
        page.get_by_role('button',name='Entrar no sistema',exact=True).click()
        expect(page.get_by_role('heading',name='Visão geral')).to_be_visible()
        page.goto(self.live_server_url+'/new/products/')
        page.locator('input[name=sku]').fill('WEB-01');page.locator('input[name=name]').fill('Produto navegador Django')
        page.locator('input[name=price]').fill('19.90')
        page.locator('input[name=minimum]').fill('2')
        page.get_by_role('button',name='Salvar produto',exact=True).click()
        expect(page.get_by_role('cell',name='Produto navegador Django',exact=True)).to_be_visible()
        page.goto(self.live_server_url+'/move/')
        page.locator('select[name=product]').select_option(label='Produto navegador Django (WEB-01)');page.locator('select[name=location]').select_option(str(location.pk))
        page.locator('select[name=kind]').select_option('entry');page.locator('input[name=quantity]').fill('5')
        page.locator('input[name=note]').fill('Recebimento navegador');page.locator('input[name=unit_cost]').fill('10')
        page.get_by_role('button',name='Confirmar',exact=True).click()
        expect(page.get_by_role('cell',name='Recebimento navegador',exact=True)).to_be_visible()
        page.goto(self.live_server_url+'/move/')
        page.locator('select[name=product]').select_option(label='Produto navegador Django (WEB-01)');page.locator('select[name=location]').select_option(str(location.pk))
        page.locator('select[name=kind]').select_option('exit');page.locator('input[name=quantity]').fill('6');page.locator('input[name=note]').fill('Saída teste')
        page.get_by_role('button',name='Confirmar',exact=True).click()
        expect(page.locator('.errorlist')).to_contain_text('Saldo disponível insuficiente')
        page.locator('input[name=quantity]').fill('3');page.get_by_role('button',name='Confirmar',exact=True).click()
        expect(page.get_by_role('cell',name='Saída teste',exact=True)).to_be_visible()
        page.goto(self.live_server_url+'/analysis/')
        page.get_by_role('button',name='Filtrar',exact=True).click()
        expect(page.get_by_role('cell',name='Produto navegador Django',exact=True)).to_be_visible()
        page.goto(self.live_server_url+'/')
        folder=Path(__file__).resolve().parents[1]/'docs/prototipos';folder.mkdir(exist_ok=True)
        expect(page.locator('.nav-group')).to_have_count(5)
        page.locator('summary').filter(has_text='Configurações').click()
        expect(page.get_by_role('link',name='Equipe e permissões',exact=True)).to_be_visible()
        page.locator('summary').filter(has_text='Configurações').click()
        sidebar=page.locator('#workspace-sidebar').bounding_box()
        content=page.locator('.content').bounding_box()
        self.assertGreaterEqual(content['x'],sidebar['width'])
        self.assertGreater(content['y'],page.locator('.topbar').bounding_box()['y'])
        page.screenshot(path=str(folder/'django-desktop.png'),full_page=True)
        page.set_viewport_size({'width':390,'height':844})
        self.assertTrue(page.evaluate('document.documentElement.scrollWidth<=window.innerWidth'))
        page.screenshot(path=str(folder/'django-mobile.png'),full_page=True)
        page.get_by_role('button',name='Abrir menu',exact=True).click()
        expect(page.locator('#menu-toggle')).to_have_attribute('aria-expanded','true')
        expect(page.locator('#workspace-sidebar')).to_be_visible()
        page.screenshot(path=str(folder/'django-menu-mobile.png'),full_page=True)
        page.get_by_role('button',name='Fechar menu',exact=True).click()
        expect(page.locator('#menu-toggle')).to_have_attribute('aria-expanded','false')
        page.get_by_role('button',name='Sair',exact=True).click()
        expect(page.get_by_role('button',name='Entrar no sistema',exact=True)).to_be_visible()
        self.assertEqual(errors,[]);page.close()

    def test_access_screen_signup_and_invalid_login(self):
        from playwright.sync_api import sync_playwright,expect
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path=os.getenv('CHROMIUM_PATH','/usr/bin/chromium'))
            try:
                page=browser.new_page(viewport={'width':1440,'height':1000},locale='pt-BR')
                page.goto(self.live_server_url+'/accounts/login/')
                expect(page.get_by_role('navigation',name='Acesso ao sistema')).to_be_visible()
                page.locator('input[name=username]').fill('unknown')
                page.locator('input[name=password]').fill('WrongPass!123')
                page.get_by_role('button',name='Entrar no sistema',exact=True).click()
                expect(page.locator('.access-errors')).to_be_visible()
                folder=Path(__file__).resolve().parents[1]/'docs/prototipos'
                page.goto(self.live_server_url+'/accounts/login/')
                page.screenshot(path=str(folder/'acesso-django-desktop.png'),full_page=True)
                page.set_viewport_size({'width':390,'height':844})
                self.assertTrue(page.evaluate('document.documentElement.scrollWidth<=window.innerWidth'))
                page.screenshot(path=str(folder/'acesso-django-mobile.png'),full_page=True)
                page.get_by_role('link',name='Cadastro',exact=True).click()
                expect(page.get_by_role('heading',name='Comece a organizar seu estoque')).to_be_visible()
                page.locator('input[name=username]').fill('signup.browser')
                page.locator('input[name=email]').fill('signup@example.test')
                page.locator('input[name=business]').fill('Negócio independente')
                page.locator('input[name=password1]').fill('SignupStrong!123')
                page.locator('input[name=password2]').fill('SignupStrong!123')
                page.screenshot(path=str(folder/'cadastro-django-mobile.png'),full_page=True)
                self.assertTrue(page.evaluate('document.documentElement.scrollWidth<=window.innerWidth'))
                page.get_by_role('button',name='Criar conta e entrar',exact=True).click()
                expect(page.get_by_role('heading',name='Visão geral')).to_be_visible()
                expect(page.locator('.workspace-account')).to_contain_text('signup.browser')
                expect(page.get_by_role('cell',name='Cadastre uma categoria e seu primeiro produto.')).to_be_visible()
                page.goto(self.live_server_url+'/new/products/')
                page.locator('input[name=sku]').fill('FIRST-01');page.locator('input[name=name]').fill('Meu primeiro produto')
                page.screenshot(path=str(folder/'produto-simples-mobile.png'),full_page=True)
                page.get_by_role('button',name='Salvar produto',exact=True).click()
                expect(page.get_by_role('cell',name='Meu primeiro produto',exact=True)).to_be_visible()
                page.get_by_role('link',name='Registrar entrada',exact=True).click()
                expect(page.locator('select[name=product]')).not_to_have_value('')
                expect(page.locator('select[name=location]')).not_to_have_value('')
            finally:browser.close()

    def test_creator_complete_pricing_and_permanent_access(self):
        from playwright.sync_api import sync_playwright,expect
        owner=get_user_model().objects.create_user('creator.ui',password='CreatorSynthetic!123',is_staff=True,is_superuser=True)
        Creator.objects.create(user=owner)
        org=Organization.objects.create(name='Negócio do Criador',trial_ends_at=timezone.now()-__import__('datetime').timedelta(days=3))
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path=os.getenv('CHROMIUM_PATH','/usr/bin/chromium'))
            try:
                page=browser.new_page(viewport={'width':1440,'height':1000},locale='pt-BR')
                page.goto(self.live_server_url+'/accounts/login/')
                page.locator('input[name=username]').fill('creator.ui');page.locator('input[name=password]').fill('CreatorSynthetic!123')
                page.get_by_role('button',name='Entrar no sistema',exact=True).click()
                page.goto(self.live_server_url+'/plans/')
                expect(page.locator('.pricing-card')).to_have_count(2)
                expect(page.locator('.workspace-account')).to_contain_text('Criador · Completo')
                expect(page.locator('.creator-plan-active')).to_have_text('✓ Completo ativo · Criador')
                expect(page.locator('#complete-price')).to_contain_text('150,00')
                page.get_by_role('button',name='6 meses',exact=False).click()
                expect(page.locator('#complete-price')).to_contain_text('750,00')
                page.get_by_role('button',name='Anual',exact=False).click()
                expect(page.locator('#complete-price')).to_contain_text('1.500,00')
                folder=Path(__file__).resolve().parents[1]/'docs/prototipos'
                page.screenshot(path=str(folder/'planos-django-desktop.png'),full_page=True)
                page.set_viewport_size({'width':390,'height':844})
                self.assertTrue(page.evaluate('document.documentElement.scrollWidth<=window.innerWidth'))
                page.screenshot(path=str(folder/'planos-django-mobile.png'),full_page=True)
                page.goto(self.live_server_url+'/subscription/')
                expect(page.get_by_role('heading',name='Completo — acesso permanente do Criador')).to_be_visible()
                expect(page.get_by_text('Não contratado',exact=True)).to_have_count(0)
                expect(page.get_by_role('button',name='Desativar renovação')).to_have_count(0)
                page.screenshot(path=str(folder/'criador-completo-mobile.png'),full_page=True)
            finally:browser.close()
