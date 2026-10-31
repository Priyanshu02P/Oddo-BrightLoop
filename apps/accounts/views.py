from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.core.paginator import Paginator
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_http_methods

from . import selectors, services, throttling
from .exceptions import EmailAlreadyRegistered
from .forms import AccountCreationForm, EmailAuthenticationForm
from .permissions import Permission, landing_url_name, require_permission

DUPLICATE_EMAIL_ERROR = (
    "This email address can't be used to create another account. "
    "If it is yours, sign in or reset your password."
)


def home(request):
    if request.user.is_authenticated:
        return redirect(landing_url_name(request.user))
    return redirect("accounts:login")


class LoginView(auth_views.LoginView):
    authentication_form = EmailAuthenticationForm
    template_name = "registration/login.html"
    redirect_authenticated_user = True

    def get_default_redirect_url(self):
        return reverse_lazy(landing_url_name(self.request.user))

    def post(self, request, *args, **kwargs):
        email = request.POST.get("username", "")
        # Check before authenticating so a throttled client cannot keep
        # guessing credentials.
        if throttling.is_throttled(throttling.LOGIN, throttling.throttle_keys(request, email)):
            form = self.authentication_form(request, initial={"username": email})
            context = self.get_context_data(form=form, throttled=True)
            return self.render_to_response(context, status=429)
        return super().post(request, *args, **kwargs)

    def form_invalid(self, form):
        throttling.record_attempt(
            throttling.LOGIN,
            throttling.throttle_keys(self.request, form.data.get("username", "")),
        )
        return super().form_invalid(form)


@require_http_methods(["GET", "POST"])
def signup(request):
    if request.user.is_authenticated:
        return redirect(landing_url_name(request.user))
    form = AccountCreationForm(request.POST or None)
    if request.method == "POST":
        keys = throttling.throttle_keys(request)
        if throttling.is_throttled(throttling.SIGNUP, keys):
            return render(
                request, "accounts/signup.html", {"form": form, "throttled": True}, status=429
            )
        throttling.record_attempt(throttling.SIGNUP, keys)
        if form.is_valid():
            try:
                services.register_customer(
                    email=form.cleaned_data["email"],
                    password=form.cleaned_data["password1"],
                )
            except EmailAlreadyRegistered:
                form.add_error("email", DUPLICATE_EMAIL_ERROR)
            else:
                messages.success(request, "Your account has been created. Please sign in.")
                return redirect("accounts:login")
    return render(request, "accounts/signup.html", {"form": form})


class PasswordResetRequestView(auth_views.PasswordResetView):
    template_name = "registration/password_reset_form.html"
    email_template_name = "registration/password_reset_email.txt"
    subject_template_name = "registration/password_reset_subject.txt"
    success_url = reverse_lazy("accounts:password_reset_done")

    def post(self, request, *args, **kwargs):
        keys = throttling.throttle_keys(request)
        if throttling.is_throttled(throttling.PASSWORD_RESET, keys):
            context = self.get_context_data(form=self.get_form(), throttled=True)
            return self.render_to_response(context, status=429)
        throttling.record_attempt(throttling.PASSWORD_RESET, keys)
        return super().post(request, *args, **kwargs)


class PasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = "registration/password_reset_confirm.html"
    success_url = reverse_lazy("accounts:password_reset_complete")


@require_permission(Permission.VIEW_DASHBOARD)
def internal_home(request):
    return render(request, "accounts/internal_home.html")


@require_permission(Permission.ACCESS_CUSTOMER_PORTAL)
def portal_home(request):
    return render(request, "accounts/portal_home.html")


@require_permission(Permission.ACCESS_CUSTOMER_PORTAL)
def portal_account(request):
    return render(request, "accounts/portal_account.html")


@require_permission(Permission.MANAGE_USERS)
def user_management(request):
    page = Paginator(selectors.list_internal_users(), 25).get_page(request.GET.get("page"))
    return render(request, "accounts/user_management.html", {"page": page})


@require_permission(Permission.CREATE_STAFF)
@require_http_methods(["GET", "POST"])
def staff_create(request):
    form = AccountCreationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            services.create_staff_account(
                actor=request.user,
                email=form.cleaned_data["email"],
                password=form.cleaned_data["password1"],
            )
        except EmailAlreadyRegistered:
            form.add_error("email", DUPLICATE_EMAIL_ERROR)
        else:
            messages.success(request, "Staff account created.")
            return redirect("accounts:user_management")
    return render(request, "accounts/staff_create.html", {"form": form})
