"""Customer portal (FR-4.7). Every lookup goes through the scoped selector, so
another customer's id is a 404, and the services check ownership again."""

from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from apps.accounts.permissions import Permission, require_permission

from . import actions, selectors


@require_permission(Permission.ACCESS_CUSTOMER_PORTAL)
def subscription_list(request):
    page = Paginator(selectors.customer_subscriptions(request.user), 25).get_page(
        request.GET.get("page")
    )
    return render(request, "subscriptions/portal_list.html", {"page": page})


@require_permission(Permission.ACCESS_CUSTOMER_PORTAL)
def subscription_detail(request, pk):
    subscription = get_object_or_404(selectors.customer_subscriptions(request.user), pk=pk)
    context = {
        "subscription": subscription,
        "actions": [
            item
            for item in actions.available_actions(subscription, internal=False)
            if item[0] in actions.PORTAL_ACTIONS
        ],
    }
    return render(request, "subscriptions/portal_detail.html", context)


@require_permission(Permission.ACCESS_CUSTOMER_PORTAL)
@require_http_methods(["GET", "POST"])
def subscription_action(request, pk, action):
    subscription = get_object_or_404(selectors.customer_subscriptions(request.user), pk=pk)
    return actions.run_action_page(
        request,
        subscription,
        action,
        allowed=actions.PORTAL_ACTIONS,
        detail_url=reverse("portal_subscriptions:subscription_detail", args=[pk]),
    )
