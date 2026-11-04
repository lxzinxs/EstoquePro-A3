from django.contrib import messages
from django.contrib.auth import login
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect, render

from ..forms import (
    MemberForm,
    MembershipForm,
    RegistrationForm,
)
from ..models import (
    Membership,
)
from ..services import (
    access_for,
    add_member,
    audit,
    change_member,
    is_creator,
    permit,
    register_business,
)
from .common import errors, page, tenant


def signup(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = RegistrationForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        try:
            user, org = register_business(
                form.cleaned_data["username"],
                form.cleaned_data["password1"],
                form.cleaned_data["email"],
                form.cleaned_data["business"],
            )
            login(request, user)
            request.session["organization_id"] = org.pk
            return redirect("dashboard")
        except (ValidationError, IntegrityError) as e:
            errors(form, e)
    return render(request, "registration/signup.html", {"form": form})


@tenant
def member(request, pk=None):
    permit(request.a, "master" if pk else "admin")
    form = (
        MembershipForm(request.POST if request.method == "POST" else None)
        if pk
        else MemberForm(request.POST if request.method == "POST" else None)
    )
    if not pk and request.a.role == "admin":
        form.fields["role"].choices = [("member", "Membro")]
        form.fields["role"].initial = "member"
        form.fields[
            "role"
        ].help_text = "Você pode adicionar membros. Somente Master ou Criador altera cargos."
    if pk:
        get_object_or_404(Membership, pk=pk, organization=request.a.organization)
    if request.method == "POST" and form.is_valid():
        try:
            if pk:
                change_member(request.a, pk, **form.cleaned_data)
            else:
                add_member(request.a, **form.cleaned_data)
            return redirect("listing", kind="members")
        except (ValidationError, IntegrityError) as e:
            errors(form, e)
    return page(
        request,
        "inventory/form.html",
        {
            "form": form,
            "title": "Gerenciar membro" if pk else "Adicionar membro",
            "help": "Admin adiciona Membros; Master e Criador também podem definir cargos. No Básico, o limite é uma conta por negócio; o Completo não tem quota comercial. O Criador é isento desses limites.",
        },
    )


@tenant
def plans(request):
    from ..catalog import PLANS

    return page(request, "inventory/plans.html", {"plans": PLANS})


@tenant
def subscription(request):
    permit(request.a, "master", write=False)
    org = request.a.organization.billing_parent or request.a.organization
    if is_creator(request.user):
        return page(request, "inventory/subscription.html", {"billing": org})
    if org.pk != request.a.organization.pk:
        permit(access_for(request.user, org.pk), "master", write=False)
    if request.method == "POST":
        org.renewal_enabled = False
        org.save(update_fields=["renewal_enabled"])
        audit(request.a, "subscription.renewal_disabled", billing_organization=org.pk)
        messages.success(
            request,
            "Renovação desativada. O acesso contratado permanece até a data de término; não há cobrança integrada nesta versão.",
        )
        return redirect("subscription")
    return page(request, "inventory/subscription.html", {"billing": org})
