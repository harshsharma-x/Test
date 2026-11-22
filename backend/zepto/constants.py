"""Constants shared by the Zepto-compatible API layer."""
from __future__ import annotations

# Store the seeded catalogue is served from. Mirrors the shape of the store id
# returned by serviceability-service / lms get_page.
DEFAULT_STORE_ID = "b4dc8d65-ed2e-4142-81b6-373982b13500"

# Cloudflare-fronted asset host used for relative CMS image paths.
CDN_BASE = "https://cdn.zeptonow.com/production/ik-seo/tr:w-600,cm-pad_resize/"

DEFAULT_LATITUDE = 19.0657
DEFAULT_LONGITUDE = 72.8687

FREE_DELIVERY_THRESHOLD_RUPEES = 149.0
DELIVERY_FEE_RUPEES = 25.0
HANDLING_FEE_RUPEES = 4.0
MAX_QUANTITY_PER_ITEM = 10

# Payment method ids as returned by the quickpay listing.
PAYMENT_METHODS = ("UPI", "CARD", "WALLET", "COD")
PREPAID_METHODS = ("UPI", "CARD", "WALLET")
