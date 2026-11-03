'use strict';
const $ = (selector) => document.querySelector(selector);
const state = {csrf: '', products: [], categories: [], suppliers: [], movements: [], dashboard: {}, page: 'dashboard', version: 0};
const labels = {dashboard: ['Visão geral', 'Os números que importam para o seu negócio.'], products: ['Produtos', 'Organize seu catálogo e acompanhe cada item.'], movements: ['Movimentações', 'Entradas e saídas com histórico e rastreabilidade.'], categories: ['Categorias', 'Um lugar para cada tipo de produto.'], suppliers: ['Fornecedores', 'Seus parceiros de abastecimento em um só lugar.'], reports: ['Relatórios', 'Transforme seu estoque em informação.']};
const esc = (value) => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));
const brl = (cents) => new Intl.NumberFormat('pt-BR', {style: 'currency', currency: 'BRL'}).format(cents / 100);
const number = (n) => new Intl.NumberFormat('pt-BR').format(n);
const date = (s) => new Intl.DateTimeFormat('pt-BR', {dateStyle: 'short', timeStyle: 'short'}).format(new Date(s.replace(' ', 'T') + 'Z'));
async function api(path, method = 'GET', body) {
  const response = await fetch('/api/' + path, {method, headers: {'Content-Type': 'application/json', 'X-CSRF-Token': state.csrf}, body: body === undefined ? undefined : JSON.stringify(body)});
  const data = await response.json();
  if (!response.ok) {
    if (response.status === 401 && !['login', 'register'].includes(path)) showLogin();
    throw new Error(data.error || 'Não foi possível concluir a operação.');
  }
  return data;
}
function toast(message, failure = false) {
  const el = $('#toast'); el.textContent = message; el.className = 'toast' + (failure ? ' failure' : ''); el.hidden = false;
  clearTimeout(toast.timer); toast.timer = setTimeout(() => el.hidden = true, 5000);
}
function showLogin() { $('#app').hidden = true; $('#login-screen').hidden = false; state.csrf = ''; selectAuthTab(false); $('#modal').close(); }
function enter(session) {
  state.csrf = session.csrf; $('#account-name').textContent = session.user.username; $('.avatar').textContent = session.user.username[0].toUpperCase();
  $('#login-screen').hidden = true; $('#app').hidden = false; loadPage();
}
$('#login-form').addEventListener('submit', async (event) => {
  event.preventDefault(); const button = event.target.querySelector('button'); button.disabled = true; $('#login-error').textContent = '';
  try { const data = Object.fromEntries(new FormData(event.target)); const session = await api('login', 'POST', data); event.target.reset(); enter(session); }
  catch (err) { $('#login-error').textContent = err.message; } finally { button.disabled = false; }
});
function selectAuthTab(register) {
  $('#login-form').hidden = register; $('#register-form').hidden = !register;
  for (const id of ['login', 'register']) {
    const active = (id === 'register') === register;
    $('#' + id + '-tab').setAttribute('aria-selected', String(active));
    $('#' + id + '-tab').tabIndex = active ? 0 : -1;
  }
  $('#login-error').textContent = ''; $('#register-error').textContent = '';
}
$('#login-tab').onclick = () => selectAuthTab(false);
$('#register-tab').onclick = () => selectAuthTab(true);
$('.auth-tabs').addEventListener('keydown', event => {
  if (['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) {
    event.preventDefault();
    const register = event.key === 'End' || (event.key !== 'Home' && $('#register-form').hidden);
    selectAuthTab(register); $('#' + (register ? 'register' : 'login') + '-tab').focus();
  }
});
$('#register-form').addEventListener('input', () => { $('#register-error').textContent = ''; });
$('#register-form').addEventListener('submit', async event => {
  event.preventDefault(); const button = event.target.querySelector('button');
  const data = Object.fromEntries(new FormData(event.target)); $('#register-error').textContent = '';
  if (data.password !== data.confirm_password) { $('#register-error').textContent = 'As senhas não coincidem.'; return; }
  button.disabled = true;
  try { const session = await api('register', 'POST', data); event.target.reset(); selectAuthTab(false); enter(session); toast('Conta criada com sucesso.'); }
  catch (err) { $('#register-error').textContent = err.message; } finally { button.disabled = false; }
});
$('#logout').addEventListener('click', async () => { try { await api('logout', 'POST', {}); showLogin(); } catch (e) { toast(e.message, true); } });
window.addEventListener('hashchange', () => { if (state.csrf) loadPage(); });
function action(label, action, cls = 'primary') { return `<button class="${cls}" data-action="${action}">${label}</button>`; }
function empty(title, detail) { return `<div class="empty"><b>${title}</b>${detail}</div>`; }
async function loadPage() {
  const version = ++state.version;
  state.page = location.hash.slice(1) in labels ? location.hash.slice(1) : 'dashboard';
  const [title, description] = labels[state.page];
  $('#page-name').textContent = title; $('#page-title').textContent = title; $('#page-description').textContent = description;
  document.querySelectorAll('nav a').forEach(a => { a.classList.toggle('active', a.dataset.page === state.page); a.setAttribute('aria-current', a.dataset.page === state.page ? 'page' : 'false'); });
  $('#page-content').innerHTML = '<div class="loading" role="status">Carregando seu estoque…</div>'; $('#page-actions').innerHTML = '';
  try {
    const [products, categories, suppliers, movements, dashboard] = await Promise.all(['products', 'categories', 'suppliers', 'movements', 'dashboard'].map(p => api(p)));
    if (version !== state.version || !state.csrf) return;
    Object.assign(state, {products, categories, suppliers, movements, dashboard}); render();
  } catch (err) { if (version === state.version && state.csrf) $('#page-content').innerHTML = empty('Não foi possível carregar', esc(err.message)) + action('Tentar novamente', 'retry', 'secondary'); }
}
function metrics() {
  const d = state.dashboard;
  return `<div class="metrics">${[
    ['Produtos ativos', number(d.products), '▣', 'Itens no seu catálogo', ''],
    ['Unidades em estoque', number(d.units), '▦', 'Saldo disponível para movimentação', ''],
    ['Valor do estoque', brl(d.value_cents), '↗', 'Calculado pelo preço de referência', 'green'],
    ['Precisam de atenção', number(d.low), '!', 'Produtos no mínimo ou abaixo', 'amber']
  ].map(([title, value, icon, note, color]) => `<div class="metric"><div class="metric-top">${title}<span class="metric-icon ${color}">${icon}</span></div><div class="metric-number">${value}</div><div class="metric-note ${color === 'green' ? 'green' : ''}">${note}</div></div>`).join('')}</div>`;
}
function status(p) { return p.quantity === 0 ? '<span class="badge zero">Sem estoque</span>' : p.quantity <= p.minimum ? '<span class="badge low">Estoque baixo</span>' : '<span class="badge ok">Disponível</span>'; }
function productRows(products, editing = false) {
  if (!products.length) return empty('Nenhum produto encontrado', 'Cadastre um produto ou ajuste os filtros de busca.');
  return `<div class="table-wrap"><table><thead><tr><th>PRODUTO</th><th>CATEGORIA</th><th>SALDO / MÍNIMO</th><th>PREÇO UNIT.</th><th>STATUS</th>${editing ? '<th>AÇÕES</th>' : ''}</tr></thead><tbody>${products.map(p => `<tr><td><div class="product-cell"><span class="product-icon" aria-hidden="true">▣</span><div><strong>${esc(p.name)}</strong><small>${esc(p.sku)}</small></div></div></td><td>${esc(p.category)}</td><td><strong>${number(p.quantity)}</strong> <span class="muted">/ ${number(p.minimum)}</span></td><td>${brl(p.price_cents)}</td><td>${status(p)}</td>${editing ? `<td><div class="row-actions"><button data-action="edit" data-id="${p.id}" aria-label="Editar ${esc(p.name)}">Editar</button><button data-action="archive" data-id="${p.id}" class="danger" aria-label="Arquivar ${esc(p.name)}">Arquivar</button></div></td>` : ''}</tr>`).join('')}</tbody></table></div>`;
}
function movementRows(items, compact = false) {
  if (!items.length) return empty('Seu histórico começa aqui', 'Registre uma entrada ou saída para acompanhar as movimentações.');
  return `<div class="table-wrap"><table><thead><tr><th>PRODUTO</th><th>TIPO</th><th>QTD.</th><th>DATA</th>${compact ? '' : '<th>SALDO APÓS</th><th>MOTIVO</th><th>USUÁRIO</th>'}</tr></thead><tbody>${items.map(m => `<tr><td><strong>${esc(m.product)}</strong><div class="metric-note">${esc(m.sku)}</div></td><td><span class="badge ${m.kind === 'entrada' ? 'in' : 'out'}">${m.kind === 'entrada' ? '↙ Entrada' : '↗ Saída'}</span></td><td>${m.kind === 'entrada' ? '+' : '−'}${number(m.quantity)}</td><td>${date(m.created_at)}</td>${compact ? '' : `<td>${number(m.balance_after)}</td><td>${esc(m.note)}</td><td>${esc(m.username)}</td>`}</tr>`).join('')}</tbody></table></div>`;
}
function render() {
  const {page, products, movements} = state;
  let html = '';
  if (page === 'dashboard') {
    $('#page-actions').innerHTML = action('↓ Exportar estoque', 'export', 'secondary') + action('＋ Nova movimentação', 'move');
    const low = products.filter(p => p.quantity <= p.minimum);
    html = metrics() + `<div class="dashboard-grid"><section class="panel"><div class="panel-heading"><div><h2>Últimas movimentações</h2><p>O que aconteceu no seu estoque</p></div><a href="#movements" class="text-button">Ver todas →</a></div>${movementRows(movements.slice(0, 5), true)}</section><section class="panel"><div class="panel-heading"><div><h2>Hora de repor</h2><p>Itens que merecem sua atenção</p></div><span class="chip">${low.length} itens</span></div><div class="panel-body">${low.length ? low.slice(0, 4).map(p => `<div class="stock-alert"><span class="product-icon">▣</span><div><strong>${esc(p.name)}</strong><small>${esc(p.sku)}</small></div><div class="stock-amount ${p.quantity === 0 ? 'zero' : ''}"><b>${number(p.quantity)} un.</b><small>Mín. ${number(p.minimum)}</small></div></div>`).join('') + '<div class="notice">Mantenha o estoque mínimo atualizado para planejar suas próximas compras.</div>' : empty('Tudo em dia', 'Nenhum produto abaixo do estoque mínimo.')}</div></section></div><section class="panel"><div class="panel-heading"><div><h2>Seu catálogo</h2><p>Uma visão rápida dos produtos</p></div><a class="text-button" href="#products">Gerenciar produtos →</a></div>${productRows(products.slice(0, 5))}<div class="table-footer">${products.length} produtos ativos no catálogo</div></section>`;
  } else if (page === 'products') {
    $('#page-actions').innerHTML = action('＋ Novo produto', 'product');
    html = `<section class="panel"><div class="toolbar"><input id="search" type="search" placeholder="Buscar por nome ou código…" aria-label="Buscar produtos"><select id="category-filter" aria-label="Filtrar categoria"><option value="">Todas as categorias</option>${options(state.categories)}</select><label><input id="low-filter" type="checkbox">Estoque baixo</label></div><div id="product-table">${productRows(products, true)}</div><div class="table-footer" id="product-count">${products.length} produtos encontrados</div></section>`;
  } else if (page === 'movements') {
    $('#page-actions').innerHTML = action('＋ Nova movimentação', 'move');
    html = `<div class="notice">Cada registro preserva o saldo após a operação. Movimentações não podem ser editadas ou excluídas; use uma nova movimentação com motivo de correção.</div><section class="panel"><div class="panel-heading"><div><h2>Histórico de movimentações</h2><p>Até 200 registros mais recentes · Horário do seu navegador</p></div></div>${movementRows(movements)}</section>`;
  } else if (page === 'categories' || page === 'suppliers') {
    const isCategory = page === 'categories';
    $('#page-actions').innerHTML = action(isCategory ? '＋ Nova categoria' : '＋ Novo fornecedor', 'lookup');
    html = state[page].length ? `<div class="lookup-grid">${state[page].map(item => `<article class="lookup-card"><span class="product-icon">${isCategory ? '▦' : '♧'}</span><div><h3>${esc(item.name)}</h3><p>${products.filter(p => p[isCategory ? 'category_id' : 'supplier_id'] === item.id).length} produtos ativos vinculados</p></div></article>`).join('')}</div>` : `<section class="panel">${empty('Vamos organizar seu estoque?', 'Use o botão acima para criar seu primeiro cadastro.')}</section>`;
  } else if (page === 'reports') {
    html = metrics() + `<section class="panel report-card"><span class="product-icon">▤</span><h2>Posição atual do estoque</h2><p>Exporte todos os produtos ativos com código, categoria, fornecedor, saldo, estoque mínimo, preço e valor total. Arquivo CSV compatível com planilhas, separado por ponto e vírgula.</p>${action('↓ Baixar relatório CSV', 'export')}<div class="notice">O valor do estoque usa o preço de referência atual de cada produto. Este relatório não é uma apuração contábil de custo nem inclui produtos arquivados.</div></section>`;
  }
  $('#page-content').innerHTML = html;
  if (page === 'products') ['#search', '#category-filter', '#low-filter'].forEach(s => $(s).addEventListener('input', filterProducts));
}
function filterProducts() {
  const q = $('#search').value.trim().toLocaleLowerCase('pt-BR'), cat = $('#category-filter').value, low = $('#low-filter').checked;
  const products = state.products.filter(p => (!q || (p.name + ' ' + p.sku).toLocaleLowerCase('pt-BR').includes(q)) && (!cat || p.category_id === Number(cat)) && (!low || p.quantity <= p.minimum));
  $('#product-table').innerHTML = productRows(products, true); $('#product-count').textContent = `${products.length} produtos encontrados`;
}
function options(items, selected = '') { return items.map(item => `<option value="${item.id}"${String(item.id) === String(selected) ? ' selected' : ''}>${esc(item.name)}</option>`).join(''); }
function field(label, name, value = '', attrs = '') { return `<label>${label}<input name="${name}" value="${esc(value)}" ${attrs}></label>`; }
function modal(title, fields, submit) {
  $('#modal-title').textContent = title; $('#modal-fields').innerHTML = fields; $('#modal-error').textContent = '';
  const form = $('#modal-form'); form.onsubmit = async (event) => {
    event.preventDefault(); const button = form.querySelector('[type=submit]'); button.disabled = true; $('#modal-error').textContent = '';
    try { await submit(Object.fromEntries(new FormData(form))); $('#modal').close(); toast('Operação concluída com sucesso.'); await loadPage(); }
    catch (err) { $('#modal-error').textContent = err.message; } finally { button.disabled = false; }
  };
  $('#modal').showModal();
}
$('#close-modal').onclick = $('#cancel-modal').onclick = () => $('#modal').close();
function productModal(id) {
  if (!state.categories.length) { toast('Cadastre uma categoria antes de adicionar produtos.', true); location.hash = 'categories'; return; }
  const p = state.products.find(p => p.id === id) || {};
  modal(id ? 'Editar produto' : 'Novo produto', field('Nome do produto', 'name', p.name || '', 'required maxlength="120"') + `<div class="form-grid">${field('Código / SKU', 'sku', p.sku || '', 'required maxlength="32"')}${field('Preço de referência (R$)', 'price', p.price_cents === undefined ? '' : (p.price_cents/100).toFixed(2), 'type="number" min="0" max="99999999" step="0.01" required')}<label>Categoria<select aria-label="Categoria" name="category_id" required><option value="">Selecione</option>${options(state.categories, p.category_id)}</select></label><label>Fornecedor<select aria-label="Fornecedor" name="supplier_id"><option value="">Sem fornecedor</option>${options(state.suppliers, p.supplier_id)}</select></label>${field('Estoque mínimo', 'minimum', p.minimum ?? 0, 'type="number" min="0" max="999999999" step="1" required')}</div><p class="form-help">O saldo é alterado somente por movimentações. Novos produtos começam com saldo zero.</p>`, data => api(id ? `products/${id}` : 'products', id ? 'PUT' : 'POST', data));
}
function movementModal() {
  if (!state.products.length) { toast('Cadastre um produto antes de movimentar o estoque.', true); location.hash = 'products'; return; }
  modal('Nova movimentação', `<label>Produto<select aria-label="Produto" name="product_id" required>${state.products.map(p => `<option value="${p.id}">${esc(p.name)} · ${esc(p.sku)} · saldo ${p.quantity}</option>`).join('')}</select></label><div class="form-grid"><label>Tipo<select aria-label="Tipo" name="kind"><option value="entrada">Entrada no estoque</option><option value="saida">Saída do estoque</option></select></label>${field('Quantidade', 'quantity', '', 'type="number" min="1" max="999999999" step="1" required')}</div>${field('Motivo', 'note', '', 'required maxlength="240" placeholder="Ex.: recebimento de mercadoria"')}<p class="form-help">Confira os dados antes de salvar. O histórico é permanente e saídas não podem ultrapassar o saldo disponível.</p>`, data => api('movements', 'POST', data));
}
document.addEventListener('click', async (event) => {
  const button = event.target.closest('[data-action]'); if (!button) return;
  const id = Number(button.dataset.id);
  switch (button.dataset.action) {
    case 'retry': return loadPage();
    case 'product': return productModal();
    case 'edit': return productModal(id);
    case 'move': return movementModal();
    case 'lookup': return modal(state.page === 'categories' ? 'Nova categoria' : 'Novo fornecedor', field('Nome', 'name', '', 'required maxlength="80"'), data => api(state.page, 'POST', data));
    case 'archive': {
      const product = state.products.find(p => p.id === id);
      if (product.quantity !== 0) return toast('Para arquivar, o produto precisa estar com saldo zero.', true);
      return modal('Arquivar produto', `<p class="muted">Arquivar <strong>${esc(product.name)}</strong>? O histórico será preservado e o código continuará reservado.</p>`, () => api(`products/${id}`, 'DELETE'));
    }
    case 'export': {
      button.disabled = true;
      try {
        const response = await fetch('/api/report.csv');
        if (!response.ok) { if (response.status === 401) showLogin(); throw new Error('Não foi possível exportar. Entre novamente e tente outra vez.'); }
        const url = URL.createObjectURL(await response.blob()), link = document.createElement('a'); link.href = url; link.download = 'estoquepro.csv'; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); toast('Relatório exportado.');
      } catch (err) { toast(err.message, true); } finally { button.disabled = false; }
    }
  }
});
api('session').then(enter).catch(() => showLogin());
