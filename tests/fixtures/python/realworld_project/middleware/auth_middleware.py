"""
Django middleware for authentication and security.

Test fixture for extract_django_middleware() - covers all middleware hooks
(process_request, process_response, process_exception, process_view, process_template_response).
"""

from django.utils.deprecation import MiddlewareMixin
from django.http import HttpResponseForbidden, HttpResponse
from django.shortcuts import redirect


# 1. Basic middleware with process_request only
class BasicAuthMiddleware(MiddlewareMixin):
    """Simple middleware that only processes requests."""

    def process_request(self, request):
        """Check authentication on every request."""
        if not request.user.is_authenticated and request.path.startswith('/admin/'):
            return HttpResponseForbidden("Authentication required")
        return None


# 2. Middleware with process_request and process_response
class SecurityHeadersMiddleware(MiddlewareMixin):
    """Add security headers to all responses."""

    def process_request(self, request):
        """Log request info."""
        request.start_time = time.time()
        return None

    def process_response(self, request, response):
        """Add security headers."""
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'

        # Log response time
        if hasattr(request, 'start_time'):
            duration = time.time() - request.start_time
            response['X-Response-Time'] = f'{duration:.2f}s'

        return response


# 3. Middleware with exception handling
class ErrorLoggingMiddleware(MiddlewareMixin):
    """Log exceptions and send alerts."""

    def process_exception(self, request, exception):
        """Log exception details (information disclosure risk)."""
        import logging
        logger = logging.getLogger(__name__)

        # SECURITY RISK: Logging full exception details
        logger.error(f"Exception on {request.path}: {exception}", exc_info=True)

        # Send email alert to admins (information disclosure)
        send_admin_email(
            subject=f"Error on {request.path}",
            message=str(exception),
            user=request.user
        )

        return None  # Let default error handler take over


# 4. Comprehensive middleware with all hooks
class ComprehensiveMiddleware(MiddlewareMixin):
    """Middleware demonstrating all Django hooks."""

    def process_request(self, request):
        """Pre-process request before view resolution."""
        # Check IP whitelist
        if not self._is_allowed_ip(request.META.get('REMOTE_ADDR')):
            return HttpResponseForbidden("IP not allowed")
        return None

    def process_view(self, request, view_func, view_args, view_kwargs):
        """Process after view resolution, before view execution."""
        # Check if view requires special permission
        if hasattr(view_func, 'special_permission_required'):
            if not request.user.has_perm(view_func.special_permission_required):
                return HttpResponseForbidden("Special permission required")
        return None

    def process_template_response(self, request, response):
        """Process template responses before rendering."""
        # Add global context variables
        if hasattr(response, 'context_data'):
            response.context_data['request_id'] = request.META.get('REQUEST_ID')
        return response

    def process_response(self, request, response):
        """Post-process response before returning to client."""
        # Add custom tracking header
        response['X-Request-ID'] = request.META.get('REQUEST_ID', 'unknown')
        return response

    def process_exception(self, request, exception):
        """Handle exceptions."""
        # Log and return custom error page
        import logging
        logging.error(f"Exception: {exception}")
        return None

    def _is_allowed_ip(self, ip):
        """Check if IP is whitelisted."""
        allowed_ips = ['127.0.0.1', '192.168.1.1']
        return ip in allowed_ips


# 5. Callable middleware (no MiddlewareMixin)
class CallableAuthMiddleware:
    """Modern callable middleware pattern."""

    def __init__(self, get_response):
        """Initialize middleware."""
        self.get_response = get_response

    def __call__(self, request):
        """Process request using callable pattern."""
        # Pre-processing
        if not self._check_auth(request):
            return HttpResponseForbidden("Auth failed")

        # Get response from next middleware/view
        response = self.get_response(request)

        # Post-processing
        response['X-Auth-Verified'] = 'true'

        return response

    def _check_auth(self, request):
        """Check authentication."""
        return request.user.is_authenticated


# 6. Minimal middleware (just process_response)
class CorsMiddleware(MiddlewareMixin):
    """Simple CORS middleware."""

    def process_response(self, request, response):
        """Add CORS headers."""
        response['Access-Control-Allow-Origin'] = '*'
        return response
