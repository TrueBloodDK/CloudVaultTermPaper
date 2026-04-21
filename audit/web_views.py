"""Веб-представление журнала аудита (только для администраторов)."""

from django.shortcuts import render, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.views import View

from audit.models import AuditLog


class AuditListView(LoginRequiredMixin, View):
    login_url = "/auth/login/"
    template_name = "audit/list.html"

    def get(self, request):
        if not request.user.is_admin:
            return redirect("files:list")

        qs = AuditLog.objects.select_related("user").all()

        q = request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(
                Q(user__email__icontains=q)
                | Q(ip_address__icontains=q)
                | Q(object_repr__icontains=q)
            )

        action = request.GET.get("action", "").strip()
        if action:
            qs = qs.filter(action=action)

        return render(request, self.template_name, {
            "logs": qs[:500],
            "action_choices": AuditLog.Action.choices,
        })
