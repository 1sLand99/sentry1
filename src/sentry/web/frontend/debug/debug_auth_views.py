from django.http import HttpRequest, HttpResponse
from django.views.generic import View

from sentry.users.models.user import User
from sentry.web.helpers import render_to_response


class DebugAuthConfirmIdentity(View):
    def get(self, request: HttpRequest) -> HttpResponse:
        auth_identity = {"id": "bar@example.com", "email": "bar@example.com"}
        return render_to_response(
            "sentry/auth-confirm-identity.html",
            context={
                "existing_user": User(email="foo@example.com"),
                "identity": auth_identity,
                "login_form": None,
                "identity_display_name": auth_identity["email"],
                "identity_identifier": auth_identity["id"],
            },
            request=request,
        )


class DebugAuthConfirmLink(View):
    def get(self, request: HttpRequest) -> HttpResponse:
        auth_identity = {"id": "bar@example.com", "email": "test1@example.com"}
        return render_to_response(
            "sentry/auth-confirm-link.html",
            context={
                "provider": "Okta",
                "existing_user": User(email="test1@example.com", avatar_type=2),
                "identity": auth_identity,
                "identity_display_name": auth_identity["email"],
                "identity_identifier": auth_identity["id"],
            },
            request=request,
        )
