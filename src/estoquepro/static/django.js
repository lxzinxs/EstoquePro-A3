'use strict';
// Atualizações periódicas autenticadas; o cursor é separado por sessão/negócio.
(() => {
 const container=document.querySelector('#live-notifications');
 if (!container)return;
 let cursor=0,initialized=false;
 async function poll(){
  try{
   const response=await fetch('/notifications/?since='+cursor,{headers:{Accept:'application/json'}});
   if(!response.ok||!response.headers.get('Content-Type')?.includes('application/json'))return;
   const data=await response.json();
   if(initialized&&data.events.length){container.textContent='Transferência atualizada. Consulte Transferências para acompanhar.';container.className='notice';}
   for(const e of data.events)cursor=Math.max(cursor,e.id);
   initialized=true;
  }catch(_){}
 }
 poll();setInterval(poll,15000);
})();

(() => {
 const scanner=document.querySelector('#barcode-scan');
 if(!scanner)return;
 scanner.addEventListener('keydown',async event=>{
  if(event.key!=='Enter')return;event.preventDefault();
  const output=document.querySelector('#barcode-result');
  try{
   const response=await fetch('/barcode/?code='+encodeURIComponent(scanner.value.trim()));
   const data=await response.json();
   if(!response.ok)throw new Error(data.error||'Código indisponível para este acesso.');
   document.querySelector('select[name=product]').value=String(data.id);output.textContent=data.name;
   document.querySelector('input[name=quantity],input[name=counted]')?.focus();
  }catch(error){output.textContent=error.message;}
 });
})();
// Menu agrupado: nativo em desktop e painel acessível em dispositivos móveis.
(() => {
 const toggle=document.querySelector('#menu-toggle'), close=document.querySelector('#menu-close'), backdrop=document.querySelector('#menu-backdrop');
 if(!toggle)return;
 function setOpen(open){
  document.body.classList.toggle('menu-open',open);toggle.setAttribute('aria-expanded',String(open));backdrop.hidden=!open;
  if(open)close.focus();else toggle.focus();
 }
 toggle.addEventListener('click',()=>setOpen(toggle.getAttribute('aria-expanded')!=='true'));
 close.addEventListener('click',()=>setOpen(false));backdrop.addEventListener('click',()=>setOpen(false));
 document.addEventListener('keydown',event=>{if(event.key==='Escape'&&document.body.classList.contains('menu-open'))setOpen(false);});
 const media=window.matchMedia('(max-width: 850px)');
 media.addEventListener('change',()=>{document.body.classList.remove('menu-open');toggle.setAttribute('aria-expanded','false');backdrop.hidden=true;});
})();
(() => {
 const price=document.querySelector('#complete-price');if(!price)return;
 const options={monthly:[15000,'/mês','Pagamento mensal, sem antecipar o ano.'],halfyear:[75000,'/6 meses','Equivalente a R$ 125/mês · economize R$ 150 no período.'],yearly:[150000,'/ano','Equivalente a R$ 125/mês · economize R$ 300 no período.']};
 document.querySelectorAll('[data-billing]').forEach(button=>button.addEventListener('click',()=>{
  const [cents,period,description]=options[button.dataset.billing];
  document.querySelectorAll('[data-billing]').forEach(item=>item.setAttribute('aria-pressed',String(item===button)));
  price.textContent=new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL'}).format(cents/100);
  document.querySelector('#complete-period').textContent=period;document.querySelector('#complete-equivalent').textContent=description;
 }));
})();
