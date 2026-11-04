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
