"""Addresses API: Saved addresses, geocoding coordinates, delivery location."""
from __future__ import annotations

import json
from typing import Any, Dict, List
from sqlalchemy.orm import Session

from backend.database.models import AccountPreference, ShoppingAccount


DEFAULT_ADDRESSES = [
    {
        "id": "addr_home_01",
        "type": "HOME",
        "name": "Home",
        "flatDetails": "Flat 402, Building B",
        "buildingName": "Emerald Heights",
        "landmark": "Near Bandra Kurla Complex",
        "city": "Mumbai",
        "pincode": "400051",
        "latitude": 19.0657,
        "longitude": 72.8687,
        "isDefault": True,
    },
    {
        "id": "addr_work_02",
        "type": "WORK",
        "name": "Work / Office",
        "flatDetails": "5th Floor, Tower 3",
        "buildingName": "One World Center",
        "landmark": "Lower Parel",
        "city": "Mumbai",
        "pincode": "400013",
        "latitude": 19.0028,
        "longitude": 72.8306,
        "isDefault": False,
    },
]


class AddressService:
    @staticmethod
    def get_addresses(db: Session, account_id: str) -> List[Dict[str, Any]]:
        pref = db.query(AccountPreference).filter(AccountPreference.account_id == account_id).first()
        if pref and pref.preferences_json:
            try:
                data = json.loads(pref.preferences_json)
                if "addresses" in data and isinstance(data["addresses"], list) and len(data["addresses"]) > 0:
                    return data["addresses"]
            except Exception:
                pass
        return DEFAULT_ADDRESSES

    @staticmethod
    def add_address(db: Session, account_id: str, new_address: Dict[str, Any]) -> List[Dict[str, Any]]:
        current = AddressService.get_addresses(db, account_id)
        if not new_address.get("id"):
            import uuid
            new_address["id"] = f"addr_{uuid.uuid4().hex[:8]}"
        current.append(new_address)

        pref = db.query(AccountPreference).filter(AccountPreference.account_id == account_id).first()
        if not pref:
            pref = AccountPreference(account_id=account_id)
            db.add(pref)

        pref.preferences_json = json.dumps({"addresses": current})
        db.commit()
        return current
