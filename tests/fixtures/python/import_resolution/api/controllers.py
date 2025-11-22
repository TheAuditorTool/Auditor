"""Controllers referencing services via relative imports."""

from ..services.user import UserService
from ..util.helpers import slugify


def register_routes(service: UserService | None = None) -> str:
    svc = service or UserService()
    slug = slugify("Admin Users")
    svc.touch(slug)
    return slug
