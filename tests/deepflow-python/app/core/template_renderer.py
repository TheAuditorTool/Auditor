"""Template renderer - HOP 13: HTML template rendering.

This is the XSS SINK. Tainted user input is inserted into
HTML templates without proper escaping.
"""

from app.utils.string_utils import clean_whitespace


class TemplateRenderer:
    """HTML template renderer.

    HOP 13: Renders HTML templates with user-controlled data.

    VULNERABILITY: XSS - User input is inserted without escaping.
    """

    def __init__(self):
        self.base_template = """
<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
</head>
<body>
    <h1>{title}</h1>
    <div class="content">
        {content}
    </div>
    <footer>
        Generated for: {user_info}
    </footer>
</body>
</html>
"""

    def render_report(self, title: str, data: dict) -> str:
        """Render report HTML.

        XSS SINK.

        Args:
            title: TAINTED report title
            data: Report data

        VULNERABILITY: Title is inserted without HTML escaping.
        Payload: <script>alert('XSS')</script>
        """
        # Process title (still TAINTED)
        title = clean_whitespace(title)

        # VULNERABLE: Direct string formatting without escaping
        html = self.base_template.format(
            title=title,  # XSS SINK - not escaped
            content=str(data),
            user_info="system",
        )

        return html

    def render_user_profile(self, username: str, bio: str) -> str:
        """Render user profile page.

        XSS SINK.

        Args:
            username: TAINTED username
            bio: TAINTED bio text

        VULNERABILITY: Both fields inserted without escaping.
        """
        template = """
<div class="profile">
    <h2>Profile: {username}</h2>
    <div class="bio">{bio}</div>
</div>
"""
        # VULNERABLE: No HTML escaping
        return template.format(
            username=username,  # XSS SINK
            bio=bio,  # XSS SINK
        )

    def render_search_results(self, query: str, results: list) -> str:
        """Render search results page.

        XSS SINK - reflects search query in output.

        Args:
            query: TAINTED search query
            results: Search results
        """
        template = """
<div class="search-results">
    <p>Results for: {query}</p>
    <ul>
        {result_items}
    </ul>
</div>
"""
        items = "".join(f"<li>{r}</li>" for r in results)

        # VULNERABLE: Query reflected without escaping
        return template.format(
            query=query,  # XSS SINK - reflected
            result_items=items,
        )

    def render_safe(self, title: str, data: dict) -> str:
        """Render with proper HTML escaping (SAFE VERSION).

        Used to demonstrate sanitized path detection.

        Args:
            title: Title to escape
            data: Report data
        """
        import html

        # SAFE: Proper HTML escaping
        safe_title = html.escape(title)

        return self.base_template.format(
            title=safe_title,  # SAFE - escaped
            content=html.escape(str(data)),
            user_info="system",
        )
