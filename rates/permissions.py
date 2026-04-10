from rest_framework.permissions import BasePermission


class IsIngestAuthenticated(BasePermission):
    """Requires that the request was authenticated via IngestTokenAuthentication."""

    def has_permission(self, request, view):
        return request.auth is not None
