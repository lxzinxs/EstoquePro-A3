"""Operações transacionais; autorização é aplicada também fora das telas."""
import calendar
import re
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction, models
from django.db.models import Sum, Q
from django.utils import timezone
from .models import *

D = Decimal

def month_after(moment, months=1):
    year, month = divmod(moment.year * 12 + moment.month - 1 + months, 12)
    return moment.replace(year=year, month=month+1, day=min(moment.day,calendar.monthrange(year,month+1)[1]))

@dataclass
class Access:
    organization: Organization
    user: object
    role: str

def is_creator(user):
    return user.is_authenticated and user.is_active and Creator.objects.filter(pk=1,user=user).exists()

def access_for(user, org_id):
    if is_creator(user):
        return Access(Organization.objects.get(pk=org_id),user,'creator')
    membership = Membership.objects.select_related('organization').filter(user=user,organization_id=org_id).first()
    if not membership: raise PermissionDenied('Você não participa deste negócio.')
    return Access(membership.organization,user,membership.role)

def permit(a, role='member', write=True, premium=False):
    if is_creator(a.user):return Organization.objects.get(pk=a.organization.pk)
    rank = {'member':0,'admin':1,'master':2}
    if not Membership.objects.filter(user=a.user,organization=a.organization,role=a.role).exists():
        raise PermissionDenied('Permissão revogada.')
    org = Organization.objects.get(pk=a.organization.pk)
    if rank[a.role] < rank[role]: raise PermissionDenied('Seu perfil não permite esta operação.')
    if write and not org.writable: raise PermissionDenied('Período encerrado. Seus dados continuam disponíveis para consulta e exportação.')
    if premium and (org.billing_parent.plan if org.billing_parent_id else org.plan) != 'complete': raise PermissionDenied('Recurso do plano Completo.')
    return org

def scoped(model, a, pk):
    try: return model.objects.get(pk=pk,organization=a.organization)
    except model.DoesNotExist: raise ValidationError('Registro inexistente neste negócio.') from None

def positive(value, zero=False):
    if isinstance(value,bool) or not re.fullmatch(r'\d{1,9}',str(value)) or int(value)<(0 if zero else 1):
        raise ValidationError('Informe uma quantidade inteira válida.')
    return int(value)

def amount(value):
    try:
        result = D(str(value))
        if not result.is_finite() or result<0 or result>999999999999 or result.as_tuple().exponent < -2: raise InvalidOperation
        return result
    except (InvalidOperation, TypeError, ValueError): raise ValidationError('Valor monetário inválido; use até duas casas decimais.') from None

def audit(a, action, **details):
    Audit.objects.create(organization=a.organization,actor=a.user,action=action,details=details)

def quantity(product, location=None, owned=False):
    lots = Lot.objects.filter(product=product)
    if location: lots=lots.filter(location=location)
    total=lots.aggregate(n=Sum('quantity'))['n'] or 0
    if owned:
        total += Transfer.objects.filter(product=product,status='pending').aggregate(n=Sum('quantity'))['n'] or 0
    return total

@transaction.atomic
def register_business(username, password, email, name):
    from django.contrib.auth.password_validation import validate_password
    user = get_user_model()(username=username.strip().lower(),email=email)
    user.full_clean(exclude=['password','last_login','date_joined'])
    validate_password(password,user)
    user.set_password(password); user.save()
    org = Organization.objects.create(name=name,trial_ends_at=month_after(timezone.now()))
    Membership.objects.create(organization=org,user=user,role='master')
    company=Company.objects.create(organization=org,name=name)
    Location.objects.create(organization=org,company=company,name='Principal')
    Schedule.objects.create(organization=org,kind='backup',interval_hours=24)
    return user,org

@transaction.atomic
def save_product(a, data, pk=None):
    org=Organization.objects.select_for_update().get(pk=a.organization.pk)
    permit(a,'admin')
    if not is_creator(a.user) and not pk and org.plan=='basic' and Product.objects.filter(organization=org,active=True).count()>=50:
        raise ValidationError('O Básico permite até 50 produtos ativos.')
    category_name=str(data.get('new_category') or '').strip()
    supplier_name=str(data.get('new_supplier') or '').strip()
    if len(category_name)>80 or len(supplier_name)>100:raise ValidationError('Nome de categoria ou fornecedor muito longo.')
    if category_name:
        category=Category.objects.filter(organization=org,name__iexact=category_name).first() or Category.objects.create(organization=org,name=category_name)
    elif data.get('category'):category=scoped(Category,a,data['category'])
    else:category=Category.objects.filter(organization=org,name__iexact='Geral').first() or Category.objects.create(organization=org,name='Geral')
    if supplier_name:
        supplier=Supplier.objects.filter(organization=org,name__iexact=supplier_name).first() or Supplier.objects.create(organization=org,name=supplier_name)
    else:supplier=scoped(Supplier,a,data['supplier']) if data.get('supplier') else None
    product=scoped(Product,a,pk) if pk else Product(organization=org)
    product.sku=str(data['sku']).strip().upper(); product.name=data['name'].strip()
    product.category=category; product.supplier=supplier
    product.price=amount(data.get('price','0')); product.minimum=positive(data.get('minimum',0),True)
    product.barcode=data.get('barcode','').strip(); product.lead_days=positive(data.get('lead_days',7),True)
    product.full_clean(); product.save(); audit(a,'product.saved',id=product.pk)
    return product

@transaction.atomic
def archive_product(a, pk):
    permit(a,'admin'); Organization.objects.select_for_update().get(pk=a.organization.pk)
    product=scoped(Product,a,pk)
    if quantity(product,owned=True): raise ValidationError('Zere os saldos e confirme transferências antes de arquivar.')
    product.active=False; product.save(update_fields=['active']); audit(a,'product.archived',id=pk)

@transaction.atomic
def move(a, product_id, location_id, kind, qty, note, unit_cost='0', lot_code='PADRAO', expiry=None):
    permit(a)
    Organization.objects.select_for_update().get(pk=a.organization.pk)
    p=scoped(Product,a,product_id); location=scoped(Location,a,location_id)
    if not p.active: raise ValidationError('Produto arquivado.')
    qty=positive(qty)
    if not isinstance(note,str) or not 1<=len(note.strip())<=240: raise ValidationError('Informe um motivo de até 240 caracteres.')
    cost=amount(unit_cost)
    if kind not in ('entry','exit'): raise ValidationError('Tipo inválido.')
    allocations=[]
    if kind=='entry':
        if not isinstance(lot_code,str) or not 1<=len(lot_code.strip())<=80: raise ValidationError('Código de lote inválido.')
        if isinstance(expiry,str):
            try: expiry=date.fromisoformat(expiry) if expiry else None
            except ValueError: raise ValidationError('Validade inválida.') from None
        old_quantity=quantity(p,owned=True)
        p.average_cost=((p.average_cost*old_quantity+cost*qty)/(old_quantity+qty)).quantize(D('.000001'))
        p.save(update_fields=['average_cost'])
        lot,created=Lot.objects.get_or_create(organization=a.organization,product=p,location=location,code=lot_code.strip(),defaults={'expiry':expiry})
        if not created and lot.expiry!=expiry: raise ValidationError('Este código de lote já tem outra validade.')
        lot.quantity+=qty; lot.save(update_fields=['quantity'])
        allocations=[{'lot':lot.pk,'code':lot.code,'expiry':str(lot.expiry) if lot.expiry else None,'quantity':qty}]
    else:
        cost=p.average_cost
        lots=list(Lot.objects.select_for_update().filter(organization=a.organization,product=p,location=location,quantity__gt=0).filter(Q(expiry__isnull=True)|Q(expiry__gte=timezone.localdate())).order_by(models.F('expiry').asc(nulls_last=True),'id'))
        if sum(l.quantity for l in lots)<qty: raise ValidationError('Saldo disponível insuficiente; lotes vencidos não podem sair por FEFO.')
        remaining=qty
        for lot in lots:
            taken=min(remaining,lot.quantity)
            if not taken: break
            lot.quantity-=taken; lot.save(update_fields=['quantity'])
            allocations.append({'lot':lot.pk,'code':lot.code,'expiry':str(lot.expiry) if lot.expiry else None,'quantity':taken})
            remaining-=taken
    movement=Movement.objects.create(organization=a.organization,product=p,location=location,actor=a.user,kind=kind,quantity=qty,unit_cost=cost,note=note.strip(),allocations=allocations)
    audit(a,'movement.created',id=movement.pk,product=p.pk,kind=kind,quantity=qty)
    return movement

@transaction.atomic
def batch_move(a, lines):
    permit(a,premium=True)
    if not isinstance(lines,list) or not 1<=len(lines)<=100: raise ValidationError('Envie entre 1 e 100 movimentações.')
    return [move(a,**line) for line in lines]

@transaction.atomic
def receive_order(a, pk):
    permit(a,'admin',premium=True)
    Organization.objects.select_for_update().get(pk=a.organization.pk)
    order=scoped(PurchaseOrder,a,pk)
    if order.status=='received': return order
    lines=list(order.lines.all())
    if not lines: raise ValidationError('Pedido sem itens.')
    total=D('0')
    for line in lines:
        scoped(Product,a,line.product_id)
        move(a,line.product_id,order.location_id,'entry',line.quantity,f'Recebimento pedido #{order.pk}',str(line.unit_cost),line.lot_code,line.expiry)
        total+=line.quantity*line.unit_cost
    if total:
        Ledger.objects.get_or_create(organization=a.organization,source_key=f'order:{order.pk}',defaults={'kind':'payable','description':f'Pedido #{order.pk}','amount':total,'due_date':timezone.localdate()})
    order.status='received';order.received_at=timezone.now();order.save()
    audit(a,'order.received',id=pk)
    return order

@transaction.atomic
def create_transfer(a,product,source,destination,qty):
    permit(a,premium=True)
    if str(source)==str(destination): raise ValidationError('Escolha locais distintos.')
    scoped(Location,a,destination)
    movement=move(a,product,source,'exit',qty,'Transferência em trânsito')
    t=Transfer.objects.create(organization=a.organization,product_id=product,source_id=source,destination_id=destination,quantity=qty,actor=a.user,allocations=movement.allocations)
    audit(a,'transfer.pending',id=t.pk)
    return t

@transaction.atomic
def confirm_transfer(a, pk):
    permit(a,premium=True); Organization.objects.select_for_update().get(pk=a.organization.pk)
    t=scoped(Transfer,a,pk)
    if t.status=='confirmed': return t
    for allocation in t.allocations:
        code=f'T{t.pk}-{allocation["code"]}'[:80]
        lot,created=Lot.objects.get_or_create(organization=a.organization,product=t.product,location=t.destination,code=code,defaults={'expiry':allocation['expiry']})
        lot.quantity+=allocation['quantity'];lot.save()
    Movement.objects.create(organization=a.organization,product=t.product,location=t.destination,actor=a.user,kind='entry',quantity=t.quantity,unit_cost=t.product.average_cost,note=f'Transferência #{t.pk} confirmada',allocations=t.allocations)
    t.status='confirmed';t.confirmed_by=a.user;t.save();audit(a,'transfer.confirmed',id=pk)
    return t

@transaction.atomic
def pay(a,pk,value,payment_date):
    permit(a,'admin',premium=True)
    ledger=Ledger.objects.select_for_update().get(pk=scoped(Ledger,a,pk).pk)
    paid=ledger.payments.aggregate(n=Sum('amount'))['n'] or D('0')
    value=amount(value)
    if value<=0 or paid+value>ledger.amount: raise ValidationError('Valor de baixa excede saldo ou é zero.')
    result=Payment.objects.create(ledger=ledger,amount=value,date=payment_date,actor=a.user)
    audit(a,'ledger.payment',id=pk,value=str(value));return result

@transaction.atomic
def add_quote(a, product, supplier, round_key, price):
    permit(a,'admin',premium=True);Organization.objects.select_for_update().get(pk=a.organization.pk)
    p=scoped(Product,a,product);s=scoped(Supplier,a,supplier)
    if Quote.objects.filter(organization=a.organization,product=p,round_key=round_key).count()>=3:
        raise ValidationError('Máximo de três fornecedores por produto e rodada.')
    q=Quote.objects.create(organization=a.organization,product=p,supplier=s,round_key=round_key,price=amount(price))
    audit(a,'quote.created',id=q.pk);return q

@transaction.atomic
def close_count(a, pk):
    permit(a,'admin',premium=True);Organization.objects.select_for_update().get(pk=a.organization.pk)
    count=scoped(StockCount,a,pk)
    if count.status=='closed': return
    lot=scoped(Lot,a,count.lot_id)
    if lot.product_id!=count.product_id or lot.location_id!=count.location_id: raise ValidationError('Lote inconsistente.')
    delta=count.counted-lot.quantity
    if delta:
        Movement.objects.create(organization=a.organization,product=lot.product,location=lot.location,actor=a.user,kind='entry' if delta>0 else 'exit',quantity=abs(delta),unit_cost=lot.product.average_cost,note=f'Ajuste de inventário #{count.pk}',allocations=[{'lot':lot.pk,'quantity':abs(delta)}])
        lot.quantity=count.counted;lot.save()
    count.status='closed';count.closed_by=a.user;count.save();audit(a,'count.closed',id=pk,difference=delta)

@transaction.atomic
def add_member(a,username,email,password,role):
    permit(a,'master');org=Organization.objects.select_for_update().get(pk=a.organization.pk)
    if role not in ('member','admin','master'): raise ValidationError('Perfil inválido.')
    if not is_creator(a.user) and org.plan=='basic' and Membership.objects.filter(organization=org).count()>=1: raise ValidationError('O Básico permite uma conta.')
    from django.contrib.auth.password_validation import validate_password
    User=get_user_model(); u=User(username=username.strip().lower(),email=email)
    validate_password(password,u);u.full_clean(exclude=['password']);u.set_password(password);u.save()
    Membership.objects.create(organization=org,user=u,role=role);audit(a,'member.created',id=u.pk,role=role)
    return u

@transaction.atomic
def change_member(a, pk, role=None, remove=False):
    permit(a,'master');Organization.objects.select_for_update().get(pk=a.organization.pk)
    m=Membership.objects.get(pk=pk,organization=a.organization)
    if m.role=='master' and (remove or role!='master') and Membership.objects.filter(organization=a.organization,role='master').count()==1:
        raise ValidationError('Não é possível remover o último Master.')
    if remove: m.delete()
    else:
        if role not in ('member','admin','master'):raise ValidationError('Perfil inválido.')
        m.role=role;m.save()
    audit(a,'member.changed',id=pk,removed=remove,role=role)

def analytics(a,start=None,end=None):
    permit(a,write=False,premium=True)
    start=start or timezone.localdate()-timedelta(days=29);end=end or timezone.localdate()
    if start>end:raise ValidationError('Período inválido.')
    events=Movement.objects.filter(organization=a.organization,created_at__date__gte=start,created_at__date__lte=end)
    rows=[]; days=(end-start).days+1
    for p in Product.objects.filter(organization=a.organization,active=True).order_by('id'):
        exits=events.filter(product=p,kind='exit').exclude(note__startswith='Transferência')
        units=sum(e.quantity for e in exits)
        consumed=sum((e.unit_cost*e.quantity for e in exits),D('0'))
        balance=quantity(p); daily=D(units)/days
        coverage=(D(balance)/daily).quantize(D('.1')) if daily else None
        suggestion=max(0,int((daily*p.lead_days+D(p.minimum)-balance).to_integral_value(rounding='ROUND_CEILING')))
        rows.append({'id':p.pk,'sku':p.sku,'name':p.name,'quantity':balance,'cost':p.average_cost,'value':p.average_cost*balance,'out':units,'consumed':consumed,'coverage':coverage,'suggestion':suggestion,'abc':'—'})
    ranked=sorted(rows,key=lambda r:r['consumed'],reverse=True);total=sum((r['consumed'] for r in rows),D('0'));cumulative=D('0')
    for r in ranked:
        if total and r['consumed']:
            share=cumulative/total;r['abc']='A' if share<D('.8') else 'B' if share<D('.95') else 'C';cumulative+=r['consumed']
    payments=Payment.objects.filter(ledger__organization=a.organization,date__range=[start,end])
    incoming=sum((p.amount for p in payments if p.ledger.kind=='receivable'),D('0'))
    outgoing=sum((p.amount for p in payments if p.ledger.kind=='payable'),D('0'))
    return {'start':start,'end':end,'rows':rows,'incoming':incoming,'outgoing':outgoing,'cash':incoming-outgoing,'consumed':total}


@transaction.atomic
def create_business(a,name):
    permit(a,'master',premium=True)
    if not isinstance(name,str) or not 1<=len(name.strip())<=120:raise ValidationError('Nome de negócio inválido.')
    parent=a.organization.billing_parent or a.organization
    Organization.objects.select_for_update().get(pk=parent.pk)
    org=Organization.objects.create(name=name.strip(),plan='complete',trial_ends_at=parent.trial_ends_at,billing_parent=parent)
    Membership.objects.create(organization=org,user=a.user,role='master')
    company=Company.objects.create(organization=org,name=name.strip())
    Location.objects.create(organization=org,company=company,name='Principal')
    audit(a,'business.created',id=org.pk)
    return org

@transaction.atomic
def reorder(a, product_id, location_id):
    permit(a,'admin',premium=True)
    Organization.objects.select_for_update().get(pk=a.organization.pk)
    p=scoped(Product,a,product_id);location=scoped(Location,a,location_id)
    if not p.supplier_id:raise ValidationError('Defina um fornecedor no produto antes de gerar pedido.')
    suggestion=next(r['suggestion'] for r in analytics(a)['rows'] if r['id']==p.pk)
    if suggestion<=0:raise ValidationError('Não há reposição sugerida para este produto.')
    order=PurchaseOrder.objects.create(organization=a.organization,supplier=p.supplier,location=location)
    PurchaseLine.objects.create(order=order,product=p,quantity=suggestion,unit_cost=p.average_cost.quantize(Decimal('.01')))
    audit(a,'order.suggested',id=order.pk,quantity=suggestion)
    return order
