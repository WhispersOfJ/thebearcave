from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from auth_app import rate_limit
from core.models import AuditLog, User


def _client_ip(request) -> str:
    return request.META.get("REMOTE_ADDR", "unknown")


def login_view(request):
    ip = _client_ip(request)

    if request.method == "POST":
        # Check lockout first
        if rate_limit.is_locked_out(ip):
            remaining = int(rate_limit.remaining_lockout_seconds(ip))
            return render(request, "auth_app/login.html", {
                "error": f"Too many failed attempts. Try again in {remaining // 60 + 1} minute(s).",
            })

        username = request.POST.get("username", "")
        password = request.POST.get("password", "")
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            rate_limit.record_failure(ip, username)
            return render(request, "auth_app/login.html", {"error": "Invalid username or password"})

        if not user.check_password(password):
            rate_limit.record_failure(ip, username)
            return render(request, "auth_app/login.html", {"error": "Invalid username or password"})

        # Successful login — log it and create session
        AuditLog.objects.create(
            action="login_success",
            detail=f"username={username} from {ip}",
        )
        request.session.cycle_key()
        request.session["user_id"] = user.id
        return redirect("/")

    return render(request, "auth_app/login.html")


@require_POST
def logout_view(request):
    request.session.pop("user_id", None)
    return redirect("auth_app:login")
