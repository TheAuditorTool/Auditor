"""
Django middleware for authentication and security.

Test fixture for extract_django_middleware() - covers all middleware hooks
(process_request, process_response, process_exception, process_view, process_template_response).
"""

from django.http import HttpResponseForbidden
from django.utils.deprecation import MiddlewareMixin


class BasicAuthMiddleware(MiddlewareMixin):
    """Simple middleware that only processes requests."""

    def process_request(self, request):
        """Check authentication on every request."""
        if not request.user.is_authenticated and request.path.startswith("/admin/"):
            return HttpResponseForbidden("Authentication required")
        return None


class SecurityHeadersMiddleware(MiddlewareMixin):
    """Add security headers to all responses."""

    def process_request(self, request):
        """Log request info."""
        request.start_time = time.time()
        return None

    def process_response(self, request, response):
        """Add security headers."""
        response["X-Content-Type-Options"] = "nosniff"
        response["X-Frame-Options"] = "DENY"
        response["X-XSS-Protection"] = "1; mode=block"

        if hasattr(request, "start_time"):
            duration = time.time() - request.start_time
            response["X-Response-Time"] = f"{duration:.2f}s"

        return response


class ErrorLoggingMiddleware(MiddlewareMixin):
    """Log exceptions and send alerts."""

    def process_exception(self, request, exception):
        """Log exception details (information disclosure risk)."""
        import logging

        logger = logging.getLogger(__name__)

        logger.error(f"Exception on {request.path}: {exception}", exc_info=True)

        send_admin_email(
            subject=f"Error on {request.path}", message=str(exception), user=request.user
        )

        return None


class ComprehensiveMiddleware(MiddlewareMixin):
    """Middleware demonstrating all Django hooks."""

    def process_request(self, request):
        """Pre-process request before view resolution."""

        if not self._is_allowed_ip(request.META.get("REMOTE_ADDR")):
            return HttpResponseForbidden("IP not allowed")
        return None

    def process_view(self, request, view_func, view_args, view_kwargs):
        """Process after view resolution, before view execution."""

        if hasattr(view_func, "special_permission_required"):
            if not request.user.has_perm(view_func.special_permission_required):
                return HttpResponseForbidden("Special permission required")
        return None

    def process_template_response(self, request, response):
        """Process template responses before rendering."""

        if hasattr(response, "context_data"):
            response.context_data["request_id"] = request.META.get("REQUEST_ID")
        return response

    def process_response(self, request, response):
        """Post-process response before returning to client."""

        response["X-Request-ID"] = request.META.get("REQUEST_ID", "unknown")
        return response

    def process_exception(self, request, exception):
        """Handle exceptions."""

        import logging

        logging.error(f"Exception: {exception}")
        return None

    def _is_allowed_ip(self, ip):
        """Check if IP is whitelisted."""
        allowed_ips = ["127.0.0.1", "192.168.1.1"]
        return ip in allowed_ips


class CallableAuthMiddleware:
    """Modern callable middleware pattern."""

    def __init__(self, get_response):
        """Initialize middleware."""
        self.get_response = get_response

    def __call__(self, request):
        """Process request using callable pattern."""

        if not self._check_auth(request):
            return HttpResponseForbidden("Auth failed")

        response = self.get_response(request)

        response["X-Auth-Verified"] = "true"

        return response

    def _check_auth(self, request):
        """Check authentication."""
        return request.user.is_authenticated


class CorsMiddleware(MiddlewareMixin):
    """Simple CORS middleware."""

    def process_response(self, request, response):
        """Add CORS headers."""
        response["Access-Control-Allow-Origin"] = "*"
        return response
