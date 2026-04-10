"""Bearer token authentication for the ingest endpoint."""

from django.conf import settings
from rest_framework import authentication, exceptions


class IngestTokenAuthentication(authentication.BaseAuthentication):
    """
    Simple bearer-token auth that checks against INGEST_BEARER_TOKEN in settings.
    No external auth service needed — tokens are configured via environment variable.
    """

    keyword = "Bearer"

    def authenticate(self, request):
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if not auth_header:
            return None

        parts = auth_header.split()
        if len(parts) != 2 or parts[0] != self.keyword:
            return None

        token = parts[1]
        if token != settings.INGEST_BEARER_TOKEN:
            raise exceptions.AuthenticationFailed("Invalid bearer token.")

        # Return a tuple of (user, auth) — we use None for user since this is
        # service-to-service auth, not user-based.
        return (None, token)
