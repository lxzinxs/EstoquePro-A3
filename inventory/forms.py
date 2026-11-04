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

class JsonForm(forms.Form):
    lines=forms.JSONField(label='Movimentações (JSON; até 100 linhas)',widget=forms.Textarea(attrs={'rows':10}),help_text='Lista com product_id, location_id, kind (entry/exit), qty, note; unit_cost e lot_code para entradas.')

class ScopedModelForm(forms.ModelForm):
    def __init__(self,*args,organization,**kwargs):
        super().__init__(*args,**kwargs)
        for field in self.fields.values():
            if isinstance(field,forms.ModelChoiceField) and hasattr(field.queryset.model,'organization'):
                field.queryset=field.queryset.filter(organization=organization)
            if isinstance(field,forms.DateField):field.widget=forms.DateInput(attrs={'type':'date'})

class ProductForm(ScopedModelForm):
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
