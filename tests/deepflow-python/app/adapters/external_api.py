"""External API adapter - HOP 9: External HTTP calls.

Makes HTTP requests to external services with SSRF vulnerability.
"""

import urllib.request
import json


class ExternalApiAdapter:
    """External API adapter for HTTP requests.

    HOP 9: Makes HTTP requests to user-controlled URLs.

    VULNERABILITY: SSRF - User can specify internal URLs.
    """

    def __init__(self):
        self.timeout = 30

    def get(self, url: str) -> dict:
        """Make GET request to URL.

        HOP 9: SSRF SINK - user-controlled URL.

        Args:
            url: TAINTED URL - SSRF vector
        """
        # VULNERABLE: No URL validation
        # User can access internal services like:
        # - http://localhost:6379 (Redis)
        # - http://169.254.169.254 (AWS metadata)
        # - http://internal-service.local

        try:
            req = urllib.request.Request(url)  # url is TAINTED
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                return {"status": response.status, "body": response.read().decode()}
        except Exception as e:
            return {"error": str(e)}

    def post(self, url: str, data: dict) -> dict:
        """Make POST request to URL.

        SSRF SINK - posts data to user-controlled URL.

        Args:
            url: TAINTED URL - SSRF vector
            data: Data to send
        """
        # VULNERABLE: No URL validation
        try:
            body = json.dumps(data).encode()
            req = urllib.request.Request(
                url,  # url is TAINTED
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                return {"status": response.status, "body": response.read().decode()}
        except Exception as e:
            return {"error": str(e)}

    def fetch_metadata(self, endpoint: str) -> dict:
        """Fetch metadata from external service.

        Args:
            endpoint: TAINTED endpoint path
        """
        base_url = "http://metadata-service"
        url = f"{base_url}/{endpoint}"  # endpoint is TAINTED
        return self.get(url)
