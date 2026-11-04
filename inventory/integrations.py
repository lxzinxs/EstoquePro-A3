"""Importação local segura de NF-e. Não transmite documentos para terceiros."""
from datetime import date
from decimal import Decimal, InvalidOperation
from defusedxml import ElementTree
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from .models import Invoice, Ledger, Product, Organization
from .services import permit, scoped, move, audit, amount

@transaction.atomic
def import_nfe(a, xml, location):
    permit(a,'admin',premium=True)
    Organization.objects.select_for_update().get(pk=a.organization.pk)
    if not isinstance(xml,bytes) or len(xml)>2*1024*1024: raise ValidationError('XML deve ter até 2 MB.')
    try: root=ElementTree.fromstring(xml)
    except Exception: raise ValidationError('XML inválido ou com entidades proibidas.') from None
    ns={'n':'http://www.portalfiscal.inf.br/nfe'}
    info=root.find('.//n:infNFe',ns)
    if info is None:raise ValidationError('XML não contém NF-e no namespace oficial.')
    key=info.get('Id','').removeprefix('NFe')
    if not key.isdigit() or len(key)!=44:raise ValidationError('Chave NF-e inválida.')
    if Invoice.objects.filter(organization=a.organization,key=key).exists():raise ValidationError('Esta NF-e já foi importada.')
    total=amount(info.findtext('n:total/n:ICMSTot/n:vNF',default='',namespaces=ns))
    number=info.findtext('n:ide/n:nNF',default='',namespaces=ns)
    if not number or len(number)>20 or total<=0:raise ValidationError('Número ou valor total inválido.')
    scoped_location=scoped(__import__('inventory.models',fromlist=['Location']).Location,a,location)
    details=info.findall('n:det',ns)
    if not details or len(details)>500:raise ValidationError('NF-e sem itens ou com mais de 500 itens.')
    for detail in details:
        prod=detail.find('n:prod',ns)
        if prod is None:raise ValidationError('Item sem produto.')
        sku=(prod.findtext('n:cProd',default='',namespaces=ns)).strip().upper()
        p=Product.objects.filter(organization=a.organization,sku=sku,active=True).first()
        if not p:raise ValidationError(f'Cadastre primeiro o produto de código {sku[:32]}.')
        try:
            qty=Decimal(prod.findtext('n:qCom',default='',namespaces=ns))
            raw_price=Decimal(prod.findtext('n:vUnCom',default='',namespaces=ns))
            if not qty.is_finite() or qty<=0 or qty!=qty.to_integral_value() or not raw_price.is_finite():raise ValueError
            price=amount(raw_price.quantize(Decimal('.01')))
        except (InvalidOperation,ValueError):raise ValidationError('NF-e possui quantidade fracionária ou valor inválido; este estoque usa unidades inteiras.') from None
        tracks=prod.findall('n:rastro',ns)
        if tracks:
            summed=Decimal('0')
            for track in tracks:
                try:
                    tracked=Decimal(track.findtext('n:qLote',default='',namespaces=ns))
                    if not tracked.is_finite() or tracked<=0 or tracked!=tracked.to_integral_value():raise ValueError
                    expiry=date.fromisoformat(track.findtext('n:dVal',default='',namespaces=ns))
                except (ValueError,InvalidOperation):raise ValidationError('Rastreabilidade do lote inválida.') from None
                move(a,p.pk,scoped_location.pk,'entry',int(tracked),f'NF-e {number}',str(price),track.findtext('n:nLote',default='',namespaces=ns),expiry)
                summed+=tracked
            if summed!=qty:raise ValidationError('Quantidades dos lotes não correspondem ao item.')
        else:move(a,p.pk,scoped_location.pk,'entry',int(qty),f'NF-e {number}',str(price),'NFE-'+key[-12:])
    dues=info.findall('n:cobr/n:dup',ns)
    if dues:
        parsed=[]
        for item in dues:
            try: due=date.fromisoformat(item.findtext('n:dVenc',default='',namespaces=ns))
            except ValueError:raise ValidationError('Vencimento inválido na duplicata.') from None
            parsed.append((due,amount(item.findtext('n:vDup',default='',namespaces=ns))))
        if sum((value for _,value in parsed),Decimal('0'))!=total:raise ValidationError('Duplicatas não correspondem ao total da nota.')
    else:parsed=[(timezone.localdate(),total)]
    invoice=Invoice.objects.create(organization=a.organization,key=key,number=number,total=total)
    for i,(due,value) in enumerate(parsed):
        if value<=0:raise ValidationError('Duplicata sem valor positivo.')
        Ledger.objects.create(organization=a.organization,kind='payable',description=f'NF-e {number} / parcela {i+1}',amount=value,due_date=due,source_key=f'nfe:{key}:{i}')
    audit(a,'nfe.imported',id=invoice.pk,key=key)
    return invoice
