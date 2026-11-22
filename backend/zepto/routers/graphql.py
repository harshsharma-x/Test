"""GraphQL gateway router.

Documented endpoint
    POST /api/v1/gateway/graphql/
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.api.addresses import AddressService
from backend.database.connection import get_db
from backend.database.crypto import decrypt_data, mask_phone_number
from backend.database.models import ShoppingAccount
from backend.zepto.deps import AuthContext, optional_auth

router = APIRouter(tags=["GraphQL Gateway"])


class GraphQLRequest(BaseModel):
    """Body of POST /api/v1/gateway/graphql/."""

    operationName: Optional[str] = None
    variables: Dict[str, Any] = Field(default_factory=dict)
    query: Optional[str] = None


@router.post("/api/v1/gateway/graphql/")
def graphql_query(
    req: GraphQLRequest,
    ctx: Optional[AuthContext] = Depends(optional_auth),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Handles unified GraphQL queries from the web client (user info, app status, addresses)."""
    account = ctx.account if ctx else None
    if not account:
        account = db.query(ShoppingAccount).first()

    if account:
        raw_phone = decrypt_data(account.encrypted_mobile) or "9876542168"
        account_id = account.id
        full_name = account.display_name or "Valued Customer"
        addresses = AddressService.get_addresses(db, account.id)
        default_address = addresses[0] if addresses else None
    else:
        raw_phone = "9876542168"
        account_id = "guest_account"
        full_name = "Guest User"
        default_address = None

    return {
        "data": {
            "app": {
                "isUnderMaintenance": False,
                "minimumSupportedAppVersion": "1.0.0",
                "latestAppVersion": "2.0.0",
                "platform": "WEB",
            },
            "user": {
                "info": {
                    "id": account_id,
                    "fullName": full_name,
                    "mobileNumber": mask_phone_number(raw_phone),
                    "isRegistered": True,
                },
                "address": default_address,
            },
        },
        "errors": None,
    }


@router.get("/api/v1/gateway/graphql/")
def graphql_query_get(
    operationName: Optional[str] = None,
    ctx: Optional[AuthContext] = Depends(optional_auth),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """GET fallback for GraphQL gateway."""
    req = GraphQLRequest(operationName=operationName)
    return graphql_query(req=req, ctx=ctx, db=db)
