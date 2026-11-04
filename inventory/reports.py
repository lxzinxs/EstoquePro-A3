import csv
import io
from decimal import Decimal
from django.utils import timezone
from .models import Product
from .services import analytics,quantity,permit,is_creator

def report_rows(a,start=None,end=None):
    permit(a,write=False)
    headers=['Código','Produto','Saldo','Preço referência','Custo médio','Valor custo','Saídas','Cobertura dias','Compra sugerida','ABC']
    if a.organization.plan=='complete' or is_creator(a.user):
        data=analytics(a,start,end)
        rows=[[r['sku'],r['name'],r['quantity'],r['id'],r['cost'],r['value'],r['out'],r['coverage'],r['suggestion'],r['abc']] for r in data['rows']]
        prices=dict(Product.objects.filter(organization=a.organization).values_list('id','price'))
        for row in rows:row[3]=prices[row[3]]
    else:
        headers=headers[:4];rows=[[p.sku,p.name,quantity(p),p.price] for p in Product.objects.filter(organization=a.organization,active=True)]
    return headers,rows

def safe(value):
    if value is None:return ''
    if isinstance(value,Decimal):return float(value)
    if isinstance(value,str) and value.lstrip().startswith(('=','+','-','@')):return "'"+value
    return value

def export(a,fmt,start=None,end=None):
    headers,rows=report_rows(a,start,end)
    if fmt=='csv':
        out=io.StringIO(newline='');writer=csv.writer(out,delimiter=';');writer.writerow(headers)
        writer.writerows([[safe(v) for v in row] for row in rows]);return out.getvalue().encode('utf-8-sig'),'text/csv'
    permit(a,write=False,premium=True)
    if fmt=='xlsx':
        from openpyxl import Workbook
        book=Workbook();sheet=book.active;sheet.title='Estoque';sheet.append(headers)
        for row in rows:sheet.append([safe(v) for v in row])
        out=io.BytesIO();book.save(out);return out.getvalue(),'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    if fmt=='pdf':
        from reportlab.lib.pagesizes import landscape,A4
        from reportlab.pdfgen import canvas
        out=io.BytesIO();page=canvas.Canvas(out,pagesize=landscape(A4));width,height=landscape(A4)
        y=height-40
        def heading():
            nonlocal y
            from django.conf import settings
            logo=(settings.PRIVATE_ROOT/a.organization.logo_file).resolve() if a.organization.logo_file else None
            if logo and logo.is_relative_to(settings.PRIVATE_ROOT.resolve()) and logo.is_file():
                page.drawImage(str(logo),width-85,height-60,width=50,height=35,preserveAspectRatio=True,mask='auto')
            page.setFont('Helvetica-Bold',14);page.drawString(30,y,'EstoquePro / '+a.organization.name[:65]);y-=22
            page.setFont('Helvetica',8);page.drawString(30,y,'Posição de estoque e análises / '+str(timezone.localdate()));y-=25
            for i,h in enumerate(headers):page.drawString(30+i*78,y,h[:17])
            y-=20
        heading();page.setFont('Helvetica',7)
        for row in rows:
            if y<40:page.showPage();y=height-40;heading();page.setFont('Helvetica',7)
            for i,value in enumerate(row):page.drawString(30+i*78,y,str(value if value is not None else '—')[:20])
            y-=17
        page.save();return out.getvalue(),'application/pdf'
    raise ValueError('Formato desconhecido')
