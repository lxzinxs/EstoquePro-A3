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
        page.get_by_role('button',name='Entrar',exact=True).click()
        expect(page.get_by_role('heading',name='Visão geral')).to_be_visible()
        page.goto(self.live_server_url+'/new/products/')
        page.locator('input[name=sku]').fill('WEB-01');page.locator('input[name=name]').fill('Produto navegador Django')
        page.locator('select[name=category]').select_option(str(category.pk));page.locator('input[name=price]').fill('19.90')
        page.locator('input[name=minimum]').fill('2');page.locator('input[name=lead_days]').fill('7')
        page.get_by_role('button',name='Confirmar',exact=True).click()
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
        page.screenshot(path=str(folder/'django-desktop.png'),full_page=True)
        page.set_viewport_size({'width':390,'height':844})
        self.assertTrue(page.evaluate('document.documentElement.scrollWidth<=window.innerWidth'))
        page.screenshot(path=str(folder/'django-mobile.png'),full_page=True)
        page.get_by_role('button',name='Sair',exact=True).click()
        expect(page.get_by_role('button',name='Entrar',exact=True)).to_be_visible()
        self.assertEqual(errors,[]);page.close()
