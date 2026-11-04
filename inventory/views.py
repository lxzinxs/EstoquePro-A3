import json
from datetime import date
from decimal import Decimal
from functools import wraps
from urllib.parse import urlencode
from django import forms
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import IntegrityError,transaction
from django.db.models import Sum
from django.http import JsonResponse,HttpResponse,FileResponse,Http404
from django.shortcuts import render,redirect,get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from .models import *
from .services import *
from .forms import *
from .integrations import import_nfe
from .reports import export

COLLECTIONS={
 'products':(Product,'Produtos',['sku','name','price','minimum'],['sku','name','category','supplier','barcode','price','minimum','lead_days']),
 'categories':(Category,'Categorias',['name'],['name']),
 'suppliers':(Supplier,'Fornecedores',['name','email','phone'],['name','email','phone']),
 'companies':(Company,'Filiais',['name'],['name']),
 'locations':(Location,'Locais e atendimento',['name','company','kind'],['name','company','kind']),
 'orders':(PurchaseOrder,'Pedidos de compra',['id','supplier','location','status'],['supplier','location']),
 'lines':(PurchaseLine,'Itens de pedido',['order','product','quantity','unit_cost'],['order','product','quantity','unit_cost','lot_code','expiry']),
 'ledger':(Ledger,'Financeiro',['id','kind','description','amount','due_date'],['kind','description','amount','due_date']),
 'quotes':(Quote,'Cotações e preços',['product','supplier','round_key','price','created_at'],['product','supplier','round_key','price']),
 'counts':(StockCount,'Inventário cego',['id','location','product','counted','status'],['location','product','lot','counted']),
 'movements':(Movement,'Histórico completo',['id','product','location','kind','quantity','unit_cost','note','actor','created_at'],None),
 'lots':(Lot,'Lotes e validade',['product','location','code','expiry','quantity'],None),
 'transfers':(Transfer,'Transferências',['id','product','source','destination','quantity','status'],None),
 'audit':(Audit,'Auditoria',['id','actor','action','details','created_at'],None),
 'jobs':(Job,'Tarefas e arquivos',['id','kind','status','attempts','error','created_at'],None),
 'schedules':(Schedule,'Agendamento',['kind','interval_hours','next_run','enabled'],['kind','interval_hours','next_run','enabled']),
 'members':(Membership,'Equipe',['id','user','role'],None),
}
PREMIUM=set(COLLECTIONS)-{'products','categories','movements','lots','jobs'}

def tenant(view):
    @login_required
    @wraps(view)
    def wrapped(request,*args,**kwargs):
        memberships=list(Membership.objects.filter(user=request.user).select_related('organization'))
        if is_creator(request.user):
            from types import SimpleNamespace
            memberships=[SimpleNamespace(organization=o,organization_id=o.pk) for o in Organization.objects.all()]
        if not memberships:return render(request,'inventory/no_business.html')
        org_id=request.session.get('organization_id')
        member=next((m for m in memberships if m.organization_id==org_id),memberships[0])
        request.a=access_for(request.user,member.organization_id)
        request.tenant_context={'org':request.a.organization,'role':request.a.role,'memberships':memberships,'nav':[(k,v[1]) for k,v in COLLECTIONS.items() if k!='lines' and (is_creator(request.user) or request.a.organization.plan=='complete' or k not in PREMIUM)]}
        return view(request,*args,**kwargs)
    return wrapped

def page(request,template,context):
    return render(request,template,{**request.tenant_context,**context})

def errors(form, exc):
    form.add_error(None,' '.join(exc.messages) if isinstance(exc,ValidationError) else 'Registro duplicado ou vínculo inválido.')

def signup(request):
    if request.user.is_authenticated:return redirect('dashboard')
    form=RegistrationForm(request.POST or None)
    if request.method=='POST' and form.is_valid():
        try:
            user,org=register_business(form.cleaned_data['username'],form.cleaned_data['password1'],form.cleaned_data['email'],form.cleaned_data['business'])
            login(request,user);request.session['organization_id']=org.pk;return redirect('dashboard')
        except (ValidationError,IntegrityError) as e:errors(form,e)
    return render(request,'registration/signup.html',{'form':form})

@tenant
def dashboard(request):
    products=list(Product.objects.filter(organization=request.a.organization,active=True))
    rows=[{'product':p,'quantity':quantity(p),'low':quantity(p)<=p.minimum} for p in products]
    return page(request,'inventory/dashboard.html',{'rows':rows,'units':sum(r['quantity'] for r in rows),'value':sum((r['quantity']*r['product'].price for r in rows),Decimal('0')),'low':sum(r['low'] for r in rows),'events':Audit.objects.filter(organization=request.a.organization,action__startswith='transfer.').order_by('-id')[:10]})

@tenant
@require_POST
def switch(request):
    a=access_for(request.user,request.POST.get('organization'))
    request.session['organization_id']=a.organization.pk;return redirect('dashboard')

@tenant
def listing(request,kind):
    if kind not in COLLECTIONS:raise Http404
    model,title,fields,_=COLLECTIONS[kind]
    permit(request.a,'master' if kind=='members' else 'admin' if kind in ('ledger','audit','quotes','schedules') else 'member',write=False,premium=kind in PREMIUM)
    query=model.objects.filter(organization=request.a.organization) if model!=PurchaseLine else model.objects.filter(order__organization=request.a.organization)
    if kind=='products':
        query=query.filter(active=True)
        if request.GET.get('q'):query=query.filter(Q(name__icontains=request.GET['q'])|Q(sku__icontains=request.GET['q'])|Q(barcode=request.GET['q']))
    if kind=='movements' and request.GET.get('product'):query=query.filter(product_id=request.GET['product'])
    total=query.count();from django.core.paginator import Paginator
    pagination=Paginator(query.order_by('-pk'),50).get_page(request.GET.get('page'))
    rows=[]
    for item in pagination:
        actions=[]
        if kind=='products':actions=[('Editar',reverse('edit-product',args=[item.pk])),('Arquivar',reverse('action',args=['archive',item.pk])),('Histórico',reverse('listing',args=['movements'])+'?'+urlencode({'product':item.pk}))]
        if kind=='orders':actions=[('Receber',reverse('action',args=['receive',item.pk])),('Compartilhar',reverse('order-share',args=[item.pk]))]
        if kind=='transfers' and item.status=='pending':actions=[('Confirmar',reverse('action',args=['confirm',item.pk]))]
        if kind=='ledger':actions=[('Baixar',reverse('payment',args=[item.pk]))]
        if kind=='counts' and item.status=='pending':actions=[('Fechar contagem',reverse('action',args=['count',item.pk]))]
        if kind=='jobs' and item.status=='done' and item.result_file:actions=[('Baixar',reverse('job-file',args=[item.pk]))]
        if kind=='members':actions=[('Permissões',reverse('membership-edit',args=[item.pk]))]
        rows.append({'cells':[getattr(item,f) for f in fields],'actions':actions})
    create=reverse('new-record',args=[kind]) if COLLECTIONS[kind][3] else reverse('add-member') if kind=='members' else None
    return page(request,'inventory/list.html',{'title':title,'headers':fields,'rows':rows,'pagination':pagination,'total':total,'create':create,'kind':kind})

@tenant
def new_record(request,kind,pk=None):
    if kind not in COLLECTIONS or COLLECTIONS[kind][3] is None:raise Http404
    model,title,_,fields=COLLECTIONS[kind]
    permit(request.a,'member' if kind=='counts' else 'admin',premium=kind in PREMIUM)
    if pk and kind!='products':raise Http404
    instance=get_object_or_404(Product,organization=request.a.organization,pk=pk) if pk else None
    Form=ProductForm if kind=='products' else forms.modelform_factory(model,form=ScopedModelForm,fields=fields)
    form=Form(request.POST or None,organization=request.a.organization,instance=instance)
    if request.method=='POST' and form.is_valid():
        try:
            with transaction.atomic():
                Organization.objects.select_for_update().get(pk=request.a.organization.pk)
                if kind=='products':
                    data={k:(v.pk if hasattr(v,'pk') else v) for k,v in form.cleaned_data.items()}
                    save_product(request.a,data,pk)
                elif kind=='quotes':
                    d=form.cleaned_data;add_quote(request.a,d['product'].pk,d['supplier'].pk,d['round_key'],d['price'])
                else:
                    item=form.save(commit=False)
                    if hasattr(item,'organization_id'):item.organization=request.a.organization
                    if kind=='lines' and item.order.status!='pending':raise ValidationError('Pedido já recebido.')
                    if kind=='counts':
                        if item.lot.product_id!=item.product_id or item.lot.location_id!=item.location_id:raise ValidationError('Lote não pertence ao produto/local escolhido.')
                        item.actor=request.user
                    if kind=='schedules' and item.interval_hours<1:raise ValidationError('Intervalo mínimo de uma hora.')
                    item.full_clean();item.save();audit(request.a,kind+'.created',id=item.pk)
            messages.success(request,'Registro salvo.');return redirect('listing',kind=kind)
        except (ValidationError,IntegrityError) as e:errors(form,e)
    return page(request,'inventory/form.html',{'form':form,'title':title})

@tenant
def movement(request):
    form=MoveForm(request.POST or None,organization=request.a.organization)
    if request.method=='POST' and form.is_valid():
        d=form.cleaned_data
        try:
            move(request.a,d['product'].pk,d['location'].pk,d['kind'],d['quantity'],d['note'],d['unit_cost'],d['lot_code'],d['expiry'])
            messages.success(request,'Movimentação registrada.');return redirect('listing',kind='movements')
        except (ValidationError,IntegrityError) as e:errors(form,e)
    return page(request,'inventory/form.html',{'form':form,'title':'Entrada / saída FEFO'})

@tenant
def batch(request):
    permit(request.a,premium=True);form=JsonForm(request.POST or None)
    if request.method=='POST' and form.is_valid():
        try:batch_move(request.a,form.cleaned_data['lines']);messages.success(request,'Lote de movimentações concluído.');return redirect('listing',kind='movements')
        except (ValidationError,IntegrityError,TypeError,KeyError) as e:errors(form,e if isinstance(e,ValidationError) else ValidationError('Formato das linhas inválido.'))
    return page(request,'inventory/form.html',{'form':form,'title':'Movimentação em lote atômica'})

@tenant
def transfer(request):
    permit(request.a,premium=True)
    Form=forms.modelform_factory(Transfer,form=ScopedModelForm,fields=['product','source','destination','quantity'])
    form=Form(request.POST or None,organization=request.a.organization)
    if request.method=='POST' and form.is_valid():
        d=form.cleaned_data
        try:create_transfer(request.a,d['product'].pk,d['source'].pk,d['destination'].pk,d['quantity']);return redirect('listing',kind='transfers')
        except (ValidationError,IntegrityError) as e:errors(form,e)
    return page(request,'inventory/form.html',{'form':form,'title':'Enviar transferência para confirmação'})

@tenant
def action(request,kind,pk):
    handlers={'archive':archive_product,'receive':receive_order,'confirm':confirm_transfer,'count':close_count}
    if kind not in handlers:raise Http404
    form=forms.Form(request.POST or None)
    if request.method=='POST':
        try:handlers[kind](request.a,pk);messages.success(request,'Operação concluída.');return redirect('dashboard')
        except (ValidationError,IntegrityError) as e:errors(form,e)
    return page(request,'inventory/form.html',{'form':form,'title':'Confirmar operação','help':'Confirme para aplicar a operação. Alterações ficam registradas na auditoria.'})

@tenant
def payment(request,pk):
    permit(request.a,'admin',premium=True);get_object_or_404(Ledger,organization=request.a.organization,pk=pk);form=PaymentForm(request.POST or None)
    if request.method=='POST' and form.is_valid():
        try:pay(request.a,pk,form.cleaned_data['value'],form.cleaned_data['date']);return redirect('listing',kind='ledger')
        except (ValidationError,IntegrityError) as e:errors(form,e)
    return page(request,'inventory/form.html',{'form':form,'title':'Registrar pagamento / recebimento'})

@tenant
def nfe(request):
    permit(request.a,'admin',premium=True);form=NfeForm(request.POST or None,request.FILES or None,organization=request.a.organization)
    if request.method=='POST' and form.is_valid():
        try:import_nfe(request.a,form.cleaned_data['xml'].read(2*1024*1024+1),form.cleaned_data['location'].pk);messages.success(request,'NF-e importada com estoque e contas a pagar.');return redirect('listing',kind='ledger')
        except (ValidationError,IntegrityError) as e:errors(form,e)
    return page(request,'inventory/form.html',{'form':form,'title':'Importar NF-e (XML)','help':'Produtos devem estar cadastrados com o mesmo código cProd. Importação duplicada é recusada.'})

@tenant
def member(request,pk=None):
    permit(request.a,'master');form=MembershipForm(request.POST or None) if pk else MemberForm(request.POST or None)
    if pk:get_object_or_404(Membership,pk=pk,organization=request.a.organization)
    if request.method=='POST' and form.is_valid():
        try:
            if pk:change_member(request.a,pk,**form.cleaned_data)
            else:add_member(request.a,**form.cleaned_data)
            return redirect('listing',kind='members')
        except (ValidationError,IntegrityError) as e:errors(form,e)
    return page(request,'inventory/form.html',{'form':form,'title':'Gerenciar membro' if pk else 'Nova conta da equipe'})

@tenant
def analysis(request):
    permit(request.a,write=False,premium=True)
    form=forms.Form(request.GET or None);form.fields['start']=forms.DateField(required=False,widget=forms.DateInput(attrs={'type':'date'}),label='Início');form.fields['end']=forms.DateField(required=False,widget=forms.DateInput(attrs={'type':'date'}),label='Fim')
    data=None
    if form.is_valid():
        try:data=analytics(request.a,form.cleaned_data['start'],form.cleaned_data['end'])
        except ValidationError as e:errors(form,e)
    return page(request,'inventory/analysis.html',{'form':form,'data':data,'locations':Location.objects.filter(organization=request.a.organization)})

@tenant
def report(request,fmt):
    if fmt not in ('csv','xlsx','pdf'):raise Http404
    try:
        start=date.fromisoformat(request.GET['start']) if request.GET.get('start') else None
        end=date.fromisoformat(request.GET['end']) if request.GET.get('end') else None
        data,mime=export(request.a,fmt,start,end)
    except (ValueError,ValidationError):return HttpResponse('Período ou formato inválido.',status=400)
    return HttpResponse(data,content_type=mime,headers={'Content-Disposition':f'attachment; filename="nerythstock.{fmt}"'})

@tenant
@require_POST
def queue(request,kind):
    if kind not in ('report','backup','briefing'):raise Http404
    permit(request.a,'master' if kind=='backup' else 'admin',premium=kind!='backup')
    job=Job.objects.create(organization=request.a.organization,kind=kind,requested_by=request.user,payload={'format':'pdf'})
    audit(request.a,'job.queued',id=job.pk,kind=kind);return redirect('listing',kind='jobs')

@tenant
def job_file(request,pk):
    job=get_object_or_404(Job,pk=pk,organization=request.a.organization,status='done')
    permit(request.a,'master' if job.kind=='backup' else 'admin',write=False)
    from django.conf import settings
    path=(settings.PRIVATE_ROOT/job.result_file).resolve()
    if not path.is_relative_to(settings.PRIVATE_ROOT.resolve()) or not path.is_file():raise Http404
    return FileResponse(path.open('rb'),as_attachment=True,filename=path.name)

@tenant
def share_order(request,pk):
    permit(request.a,'admin',write=False,premium=True);order=get_object_or_404(PurchaseOrder,organization=request.a.organization,pk=pk)
    text=f'EstoquePro / Pedido #{order.pk}\n'+ '\n'.join(f'{l.product.sku}: {l.quantity} x R$ {l.unit_cost}' for l in order.lines.select_related('product'))
    phone=''.join(c for c in order.supplier.phone if c.isdigit())
    return page(request,'inventory/share.html',{'text':text,'share_url':'https://wa.me/'+phone+'?'+urlencode({'text':text})})

@tenant
def labels(request):
    permit(request.a,write=False,premium=True)
    from reportlab.graphics.barcode import code128
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen.canvas import Canvas
    import io
    out=io.BytesIO();c=Canvas(out,pagesize=A4);y=800
    for p in Product.objects.filter(organization=request.a.organization,active=True).exclude(barcode=''):
        if y<100:c.showPage();y=800
        if len(p.barcode)>32:continue
        c.drawString(30,y,p.name[:60]);code128.Code128(p.barcode,barHeight=35,barWidth=.6).drawOn(c,30,y-45);c.drawString(30,y-60,p.barcode);y-=100
    c.save();return HttpResponse(out.getvalue(),content_type='application/pdf',headers={'Content-Disposition':'attachment; filename="etiquetas.pdf"'})

@tenant
def notifications(request):
    permit(request.a,write=False)
    try:since=max(0,int(request.GET.get('since','0')))
    except ValueError:since=0
    events=Audit.objects.filter(organization=request.a.organization,action__startswith='transfer.',id__gt=since).order_by('id')[:100]
    return JsonResponse({'events':[{'id':e.pk,'action':e.action,'details':e.details} for e in events]})


@tenant
def business(request):
    permit(request.a,'master',premium=True)
    form=forms.Form(request.POST or None);form.fields['name']=forms.CharField(label='Nome do novo negócio',max_length=120)
    if request.method=='POST' and form.is_valid():
        try:
            org=create_business(request.a,form.cleaned_data['name']);request.session['organization_id']=org.pk
            return redirect('dashboard')
        except (ValidationError,IntegrityError) as e:errors(form,e)
    return page(request,'inventory/form.html',{'form':form,'title':'Novo negócio com dados isolados'})

@tenant
def branding(request):
    permit(request.a,'master',premium=True)
    form=forms.Form(request.POST or None,request.FILES or None);form.fields['logo']=forms.ImageField(label='Logo PNG ou JPEG')
    if request.method=='POST' and form.is_valid():
        from PIL import Image
        from django.conf import settings
        import uuid
        upload=form.cleaned_data['logo']
        if upload.size>2*1024*1024:form.add_error('logo','Tamanho máximo de 2 MB.')
        else:
            try:
                image=Image.open(upload)
                if image.format not in ('PNG','JPEG') or image.width>2000 or image.height>2000:raise ValueError
                path=settings.PRIVATE_ROOT/str(request.a.organization.pk)/('logo-'+uuid.uuid4().hex+'.png')
                path.parent.mkdir(parents=True,exist_ok=True);image.convert('RGB').save(path,'PNG');path.chmod(0o600)
                request.a.organization.logo_file=str(path.relative_to(settings.PRIVATE_ROOT));request.a.organization.save(update_fields=['logo_file'])
                audit(request.a,'brand.updated');messages.success(request,'Marca atualizada.');return redirect('dashboard')
            except (OSError,ValueError):form.add_error('logo','Use PNG/JPEG de até 2000 x 2000 pixels.')
    return page(request,'inventory/form.html',{'form':form,'title':'Marca nos relatórios'})

@login_required
def plans(request):
    from src.estoquepro.plans import PLANS
    return render(request,'inventory/plans.html',{'plans':PLANS})

@tenant
def subscription(request):
    permit(request.a,'master',write=False)
    org=request.a.organization.billing_parent or request.a.organization
    if org.pk!=request.a.organization.pk and not is_creator(request.user):access_for(request.user,org.pk)
    if request.method=='POST':
        org.renewal_enabled=False;org.save(update_fields=['renewal_enabled'])
        audit(request.a,'subscription.renewal_disabled',billing_organization=org.pk)
        messages.success(request,'Renovação desativada. O acesso contratado permanece até a data de término; não há cobrança integrada nesta versão.')
        return redirect('subscription')
    return page(request,'inventory/subscription.html',{'billing':org})

@tenant
@require_POST
def suggested_order(request,pk):
    try:
        order=reorder(request.a,pk,request.POST.get('location'));return redirect('order-share',pk=order.pk)
    except (ValidationError,IntegrityError) as exc:
        messages.error(request,' '.join(exc.messages) if isinstance(exc,ValidationError) else 'Não foi possível criar o pedido.')
        return redirect('analysis')

@tenant
def barcode(request):
    permit(request.a,write=False,premium=True)
    product=Product.objects.filter(organization=request.a.organization,active=True,barcode=request.GET.get('code','')).exclude(barcode='').first()
    if not product:return JsonResponse({'error':'Código não cadastrado neste negócio.'},status=404)
    return JsonResponse({'id':product.pk,'name':product.name})
