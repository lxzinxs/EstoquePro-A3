'use strict';
(() => {
  const dialog = document.querySelector('#plans-dialog');
  const target = document.querySelector('#plans-content');
  const escape = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let catalog;
  async function show() {
    if (!dialog.open) dialog.showModal();
    target.innerHTML = '<p class="loading" role="status">Carregando planos…</p>';
    try {
      if (!catalog) {
        const response = await fetch('/api/plans');
        if (!response.ok) throw new Error('Não foi possível carregar os planos.');
        catalog = (await response.json()).plans;
      }
      target.innerHTML = '<div class="plan-grid">' + catalog.map((plan, index) => {
        const predecessor = catalog.find(p => p.id === plan.inherits);
        const groups = [...new Set(plan.features.map(f => f.group))];
        const limits = plan.accounts === null ? 'Contas e produtos ilimitados' : `${plan.accounts} ${plan.accounts === 1 ? 'conta' : 'contas'} · ${plan.products} produtos`;
        return `<article class="plan-card plan-${escape(plan.id)}"><p class="plan-number">0${index+1} / ${index ? 'EVOLUIR' : 'COMEÇAR'}</p><h3>${escape(plan.name)}</h3><p class="plan-description">${escape(plan.description)}</p><div class="plan-price">${new Intl.NumberFormat('pt-BR', {style:'currency',currency:'BRL'}).format(plan.price_cents/100) + '<span>/mês</span>'}</div><p class="plan-limits">${escape(limits)}</p><p class="plan-inherits">${predecessor ? `Tudo do ${escape(predecessor.name)}, mais:` : 'O essencial para o seu estoque:'}</p>${groups.map(group => `<section class="plan-feature-group"><h4>${escape(group)}</h4><ul>${plan.features.filter(f=>f.group===group).map(feature=>`<li><span aria-hidden="true">${feature.available?'✓':'○'}</span><div>${escape(feature.name)}<small class="feature-state ${feature.available?'available':''}">${feature.available?'Disponível no aplicativo':'Planejado'}</small></div></li>`).join('')}</ul></section>`).join('')}</article>`;
      }).join('') + '</div><div class="plan-bottom"><h3>Transparência em cada etapa.</h3><p>As funcionalidades disponíveis hoje continuam acessíveis no aplicativo. O lançamento dos planos depende da implantação de limites, isolamento de empresas e permissões. Integrações Google e atendimento precisam de configuração. Automações serão feitas com regras locais, sem serviços pagos de IA.</p></div>';
    } catch (error) {
      target.innerHTML = '<div class="empty"><b>Planos indisponíveis</b><p></p><button type="button" class="secondary" id="retry-plans">Tentar novamente</button></div>';
      target.querySelector('p').textContent = error.message;
      target.querySelector('button').onclick = show;
    }
  }
  document.addEventListener('click', event => { if(event.target.closest('[data-open-plans]')) show(); });
  document.querySelector('#close-plans').onclick = () => dialog.close();
})();
