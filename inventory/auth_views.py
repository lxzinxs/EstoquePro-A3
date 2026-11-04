from datetime import timedelta
from django.contrib.auth.views import LoginView
from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone
from django.utils.crypto import salted_hmac
from .models import LoginThrottle

class ProtectedLoginView(LoginView):
    @transaction.atomic
    def post(self,request,*args,**kwargs):
        key=salted_hmac('login-throttle',request.META.get('REMOTE_ADDR','')).hexdigest()
        throttle,_=LoginThrottle.objects.get_or_create(key=key)
        throttle=LoginThrottle.objects.select_for_update().get(pk=key)
        now=timezone.now()
        if throttle.window<now-timedelta(minutes=5):throttle.window=now;throttle.attempts=0
        if throttle.attempts>=20:return HttpResponse('Muitas tentativas. Aguarde cinco minutos.',status=429)
        throttle.attempts+=1;throttle.save()
        response=super().post(request,*args,**kwargs)
        if response.status_code==302:throttle.attempts=0;throttle.save()
        return response


from django.contrib.auth.views import PasswordResetView
from django.conf import settings
class ConfiguredPasswordResetView(PasswordResetView):
    def form_valid(self,form):
        if settings.EMAIL_BACKEND=='django.core.mail.backends.smtp.EmailBackend' and not settings.EMAIL_HOST:
            form.add_error(None,'Recuperação por e-mail ainda não configurada. Solicite auxílio ao Criador.')
            return self.form_invalid(form)
        return super().form_valid(form)
