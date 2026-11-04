from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
from .models import *

class RegistrationForm(UserCreationForm):
    email=forms.EmailField()
    business=forms.CharField(label='Nome do negócio',max_length=120)
    class Meta:
        model=get_user_model();fields=['username','email','business','password1','password2']

class MoveForm(forms.Form):
    product=forms.ModelChoiceField(queryset=Product.objects.none(),label='Produto')
    location=forms.ModelChoiceField(queryset=Location.objects.none(),label='Local')
    kind=forms.ChoiceField(choices=Movement._meta.get_field('kind').choices,label='Tipo')
    quantity=forms.IntegerField(min_value=1,max_value=999999999,label='Quantidade')
    note=forms.CharField(max_length=240,label='Motivo')
    unit_cost=forms.DecimalField(max_digits=14,decimal_places=2,min_value=0,initial=0,label='Custo unitário (entrada)')
    lot_code=forms.CharField(max_length=80,initial='PADRAO',label='Lote (entrada)')
    expiry=forms.DateField(required=False,label='Validade (entrada)',widget=forms.DateInput(attrs={'type':'date'}))
    def __init__(self,*args,organization,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['product'].queryset=Product.objects.filter(organization=organization,active=True)
        self.fields['location'].queryset=Location.objects.filter(organization=organization).select_related('company')
        if self.fields['location'].queryset.count()==1:self.fields['location'].initial=self.fields['location'].queryset.first()
        self.fields['unit_cost'].help_text='Informe o custo de uma unidade na compra. Na saída, o custo médio é calculado automaticamente.'
        self.fields['lot_code'].help_text='Use PADRAO se não controla lotes. Na saída, o sistema escolhe por validade (FEFO).'
        self.fields['expiry'].help_text='Opcional. Deixe em branco para produtos sem validade.'
        self.fields['note'].widget.attrs['placeholder']='Ex.: Compra recebida, venda ou consumo interno'

class JsonForm(forms.Form):
    lines=forms.JSONField(label='Movimentações (JSON; até 100 linhas)',widget=forms.Textarea(attrs={'rows':10}),help_text='Lista com product_id, location_id, kind (entry/exit), qty, note; unit_cost e lot_code para entradas.')

class ScopedModelForm(forms.ModelForm):
    def __init__(self,*args,organization,**kwargs):
        super().__init__(*args,**kwargs)
        labels={'sku':'Código do produto (SKU)','name':'Nome','category':'Categoria','supplier':'Fornecedor','barcode':'Código de barras','price':'Preço de referência (R$)','minimum':'Estoque mínimo','lead_days':'Prazo de reposição (dias)','email':'E-mail','phone':'Telefone / WhatsApp','company':'Filial','kind':'Tipo','order':'Pedido de compra','product':'Produto','quantity':'Quantidade','unit_cost':'Custo unitário (R$)','lot_code':'Código do lote','expiry':'Validade','description':'Descrição','amount':'Valor (R$)','due_date':'Vencimento','round_key':'Nome da rodada de cotação','location':'Local de estoque','lot':'Lote','counted':'Quantidade contada','interval_hours':'Intervalo (horas)','next_run':'Próxima execução','enabled':'Ativo'}
        for name,field in self.fields.items():
            field.label=labels.get(name,field.label)
            if isinstance(field,forms.ModelChoiceField) and hasattr(field.queryset.model,'organization'):
                field.queryset=field.queryset.filter(organization=organization)
            if isinstance(field,forms.DateField):field.widget=forms.DateInput(attrs={'type':'date'})

class ProductForm(ScopedModelForm):
    new_category=forms.CharField(label='Criar categoria agora',max_length=80,required=False,help_text='Opcional. Se preencher, usaremos esta categoria no lugar da seleção.')
    new_supplier=forms.CharField(label='Criar fornecedor agora',max_length=100,required=False,help_text='Opcional. Você também pode adicionar o fornecedor depois.')
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['category'].required=False
        self.fields['category'].empty_label='Geral (padrão)'
        self.fields['supplier'].required=False
        self.fields['supplier'].empty_label='Sem fornecedor'
        self.fields['price'].initial=0
        self.fields['price'].help_text='Preço de venda ou referência. O custo de compra é informado na entrada de estoque.'
        self.fields['barcode'].help_text='Opcional: escaneie ou digite o código que está na embalagem.'
        self.fields['minimum'].help_text='Avisaremos quando o saldo atingir este número. Use zero se não houver mínimo.'
        self.fields['lead_days'].help_text='Usado nas sugestões de compra. Pode ser ajustado depois.'
        self.fields['sku'].widget.attrs['placeholder']='Ex.: PROD-001'
        self.fields['name'].widget.attrs['placeholder']='Ex.: Caderno A5'
    class Meta:
        model=Product;fields=['sku','name','category','supplier','barcode','price','minimum','lead_days']

class NfeForm(forms.Form):
    xml=forms.FileField(label='XML da NF-e')
    location=forms.ModelChoiceField(queryset=Location.objects.none(),label='Local de recebimento')
    def __init__(self,*args,organization,**kwargs):
        super().__init__(*args,**kwargs);self.fields['location'].queryset=Location.objects.filter(organization=organization)

class MemberForm(forms.Form):
    username=forms.CharField(max_length=150,label='Usuário')
    email=forms.EmailField()
    password=forms.CharField(widget=forms.PasswordInput,label='Senha inicial')
    role=forms.ChoiceField(choices=Membership._meta.get_field('role').choices,label='Perfil')

class MembershipForm(forms.Form):
    role=forms.ChoiceField(choices=Membership._meta.get_field('role').choices,label='Perfil')
    remove=forms.BooleanField(required=False,label='Remover membro do negócio')

class PaymentForm(forms.Form):
    value=forms.DecimalField(max_digits=14,decimal_places=2,min_value=.01,label='Valor da baixa')
    date=forms.DateField(label='Data',widget=forms.DateInput(attrs={'type':'date'}))
