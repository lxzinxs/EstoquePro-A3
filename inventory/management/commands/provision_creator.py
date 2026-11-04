import getpass
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand,CommandError
from django.db import transaction
from inventory.models import Creator,Organization,Company,Location
from inventory.services import month_after
from django.utils import timezone

class Command(BaseCommand):
    help='Provisiona o único Criador. A senha é solicitada sem eco e nunca é gravada em arquivos.'
    def add_arguments(self,parser):parser.add_argument('--username',required=True)
    @transaction.atomic
    def handle(self,*args,**options):
        name=options['username']
        existing=Creator.objects.select_for_update().filter(pk=1).select_related('user').first()
        if existing and existing.user.username!=name:raise CommandError('Já existe outro Criador. Nenhum acesso foi alterado.')
        password=getpass.getpass('Senha do Criador: ')
        confirmation=getpass.getpass('Confirme a senha: ')
        if password!=confirmation:raise CommandError('As senhas não coincidem.')
        if len(password)<12:raise CommandError('Use pelo menos 12 caracteres.')
        User=get_user_model();user=User.objects.filter(username=name).first() or User(username=name)
        user.set_password(password);user.is_active=True;user.is_superuser=True;user.is_staff=True;user.save()
        Creator.objects.get_or_create(pk=1,defaults={'user':user})
        if not Organization.objects.exists():
            org=Organization.objects.create(name='EstoquePro',trial_ends_at=month_after(timezone.now()))
            company=Company.objects.create(organization=org,name='Principal')
            Location.objects.create(organization=org,company=company,name='Principal')
        from django.contrib.sessions.models import Session
        for session in Session.objects.filter(expire_date__gt=timezone.now()).iterator():
            if session.get_decoded().get('_auth_user_id')==str(user.pk):session.delete()
        self.stdout.write(self.style.SUCCESS('Criador provisionado. Senha armazenada com o hash padrão do Django.'))
