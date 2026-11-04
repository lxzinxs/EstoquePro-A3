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
      target.innerHTML = '<div class="plan-grid two-plans">' + catalog.map((plan, index) => {
        const predecessor = catalog.find(p => p.id === plan.inherits);
        const groups = [...new Set(plan.features.map(f => f.group))];
        const limits = plan.accounts === null ? 'Contas e produtos ilimitados' : `${plan.accounts} ${plan.accounts === 1 ? 'conta' : 'contas'} · ${plan.products} produtos`;
        return `<article class="plan-card plan-${escape(plan.id)}"><p class="plan-number">0${index+1} / ${index ? 'EVOLUIR' : 'COMEÇAR'}</p><h3>${escape(plan.name)}</h3><p class="plan-description">${escape(plan.description)}</p><div class="plan-price">${new Intl.NumberFormat('pt-BR', {style:'currency',currency:'BRL'}).format(plan.price_cents/100) + (plan.trial_months ? '<span>por 1 mês</span>' : '<span>/mês</span>')}</div><p class="plan-limits">${escape(limits)}</p>${plan.trial_months ? '<div class="plan-terms">Acesso gratuito por um mês. Depois, é necessário contratar o Completo; não há conversão automática nem cobrança nesta versão.</div>' : '<div class="billing-choices"><h4>Escolha o período</h4>' + plan.billing_options.map(option => '<div class="billing-choice"><strong>' + escape(option.id === 'mensal' ? 'Mensal' : option.id === 'semestral' ? '6 meses' : '12 meses') + '</strong><span>' + new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL'}).format(option.total_cents/100) + (option.months === 1 ? '/mês' : ' pelo período · equivalente a R$ 125/mês') + '</span></div>').join('') + '<div class="plan-terms">Condições propostas: plano semestral com prazo de cancelamento antecipado de 2 meses de uso; anual, de 3 meses. Após esse prazo, o período contratado permanece até o fim. A renovação pode ser desativada. Condições de reembolso e direitos legais precisam ser definidos no contrato antes da contratação.</div></div>'}<p class="plan-inherits">${predecessor ? `Tudo do ${escape(predecessor.name)}, mais:` : 'O essencial para o seu estoque:'}</p>${groups.map(group => `<section class="plan-feature-group"><h4>${escape(group)}</h4><ul>${plan.features.filter(f=>f.group===group).map(feature=>`<li><span aria-hidden="true">${feature.available?'✓':'○'}</span><div>${escape(feature.name)}<small class="feature-state ${feature.available?'available':''}">${feature.available?'Disponível no aplicativo':'Planejado'}</small></div></li>`).join('')}</ul></section>`).join('')}</article>`;
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
