"""FastAPI router showcasing dependency injection and response models."""
# ruff: noqa: B008 - FastAPI Depends() pattern is intentional

from fastapi import APIRouter, Depends

from ..services.accounts import AccountService
from ..validators.accounts import AccountPayload, AccountResponse
from .deps import get_db, get_email_service, get_repository

router = APIRouter(prefix="/api", tags=["users"])


@router.get("/users", response_model=list[AccountResponse])
def list_users(
    repository=Depends(get_repository),
) -> list[AccountResponse]:
    """Return all accounts as API-friendly payloads."""

    service = AccountService(repository=repository, email_service=get_email_service())
    return [service.serialize_account(account) for account in service.list_accounts()]


@router.post("/users", response_model=AccountResponse, status_code=201)
def create_user(
    payload: AccountPayload,
    repository=Depends(get_repository),
    email_service=Depends(get_email_service),
) -> AccountResponse:
    """Create a new account and queue a welcome notification."""

    service = AccountService(repository=repository, email_service=email_service)
    created = service.register_account(payload)
    return service.serialize_account(created)


@router.get("/users/{account_id}", response_model=AccountResponse)
def get_user(
    account_id: int,
    repository=Depends(get_repository),
    _db=Depends(get_db),
) -> AccountResponse:
    """Retrieve an account by id to exercise path-parameter parsing."""

    service = AccountService(repository=repository, email_service=get_email_service())
    account = service.fetch_account(account_id)
    return service.serialize_account(account)
