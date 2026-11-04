from django.contrib import admin
from . import models
# O admin global é reservado ao Criador; o site normal aplica escopo por negócio.
admin.site.site_header='EstoquePro · Criador'
admin.site.site_title='EstoquePro'
admin.site.has_permission=lambda request: request.user.is_active and request.user.is_staff and models.Creator.objects.filter(pk=1,user=request.user).exists()
for name in ['Organization','Membership','Company','Location','Category','Supplier','Product','Lot','Movement','PurchaseOrder','PurchaseLine','Transfer','Ledger','Payment','Invoice','Quote','StockCount','Audit','Job','Schedule','LegacyImport']:
    model=getattr(models,name)
    cls=type(name+'Admin',(admin.ModelAdmin,),{'list_display':['__str__','id']})
    if name in ['Audit','Movement','LegacyImport']:
        cls.has_add_permission=lambda self,request:False
        cls.has_change_permission=lambda self,request,obj=None:False
        cls.has_delete_permission=lambda self,request,obj=None:False
    admin.site.register(model,cls)
