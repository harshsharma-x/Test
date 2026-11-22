# API documentation (observed)

Derived from captured traffic. Only endpoint metadata, parameter names and response key shapes are included - no tokens, cookies, header values or payloads.

## account

### `GET /api/v1/pass/overview`

- host: `bff-gateway.zepto.com`
- calls observed: 6
- status codes: 200×6
- query params: -
- auth indicators: app request signature, csrf secret header, csrf token header, session header
- response keys: `{"showBadge": "bool", "showBottomsheet": "bool", "variantName": "string", "productOffers": [], "passLockedStateText": "string", "suggestedPass": "null", "membership": "null", "userCohort": "string", "lifetimeSavings": {"totalPurchaseFee": "number", "totalSavingsAmount": "number", "totalPreviousSavin`

### `GET /api/v1/user/customer/referrals/`

- host: `bff-gateway.zepto.com`
- calls observed: 1
- status codes: 200×1
- query params: -
- auth indicators: app request signature, csrf secret header, csrf token header, session header
- response keys: `{"uiSchema": {"benefitsWidget": {"advocate": "...", "receiver": "..."}, "header": {"image": "...", "subtitle": "...", "title": "..."}, "stepsToRefer": {"footer": "...", "steps": "...", "title": "..."}}, "pageLayout": "null", "referralCode": "string"}`

### `GET /api/v1/wallet-balances/total`

- host: `bff-gateway.zepto.com`
- calls observed: 1
- status codes: 200×1
- query params: includePendingGiftCardInfo
- auth indicators: app request signature, csrf secret header, csrf token header, explicit no-bearer opt-out, session header
- response keys: `{"totalBalance": "number", "availableBalance": "number", "totalPromotionalBalance": "number", "available": "bool", "hasPendingGiftCard": "bool", "totalBalanceNumericalAbbreviation": "string"}`

### `POST /api/v2/user/customer/info/`

- host: `bff-gateway.zepto.com`
- calls observed: 1
- status codes: 200×1
- query params: -
- auth indicators: app request signature, csrf secret header, csrf token header, session header
- request body keys: `{"appVersion": "string", "bundleVersion": "string", "deviceUid": "string", "platform": "string"}`
- response keys: `{"user": {"blockRefererral": "bool", "countryCode": "string", "emailId": "null", "fullName": "string", "id": "string", "isBetaUser": "null", "isInternalUser": "bool", "isInternationalUser": "bool", "isRegistered": "bool", "isUserFullNameSet": "bool", "lastOrderNotified": "bool", "mobileNumber": "str`

### `GET /coupon-service/api/v1/coupons/promo_cash`

- host: `bff-gateway.zepto.com`
- calls observed: 1
- status codes: 200×1
- query params: source
- auth indicators: app request signature, csrf secret header, csrf token header, session header
- response keys: `"null"`

### `GET /pagead/1p-user-list/{n}/`

- host: `www.google.com`
- calls observed: 1
- status codes: 200×1
- query params: _tu, async, auid, bg, cid, cv, data, dma, en, ept, fmt, frm, fst, gcd, gtm, guid, hn, ipr, is_vtc, npa, pscdl, random, rcb, rfmt, rmt_tld, tag_exp, tiba, u_h, u_w, uaa, uab, uafvl, uam, uamb, uap, uapv, uaw, url
- auth indicators: none seen

## authentication

### `GET /api/auth/create-csrf-token`

- host: `www.zepto.com`
- calls observed: 2
- status codes: 200×2
- query params: -
- auth indicators: none seen
- response keys: `{}`

### `POST /api/auth/verify-otp`

- host: `www.zepto.com`
- calls observed: 1
- status codes: 200×1
- query params: -
- auth indicators: app request signature, csrf secret header, csrf token header, session header
- request body keys: `{"mobileNumber": "string", "countryCode": "string", "otpToken": "string"}`
- response keys: `{"user": {"blockRefererral": "bool", "countryCode": "string", "emailId": "null", "fullName": "string", "id": "string", "isBetaUser": "null", "isInternalUser": "bool", "isInternationalUser": "bool", "isRegistered": "bool", "lastOrderNotified": "bool", "mobileNumber": "string", "referralCode": "string`

### `POST /api/v1/user/customer/send-otp-sms/`

- host: `bff-gateway.zepto.com`
- calls observed: 1
- status codes: 200×1
- query params: -
- auth indicators: app request signature, csrf secret header, csrf token header, session header
- request body keys: `{"mobileNumber": "string", "countryCode": "string"}`
- response keys: `{"verificationType": "string", "data": {"msg": "string"}}`

## cart

### `POST /cfs/api/v1/cart/create`

- host: `bff-gateway.zepto.com`
- calls observed: 1
- status codes: 200×1
- query params: -
- auth indicators: app request signature, csrf secret header, csrf token header, session header
- request body keys: `{"storeId": "string", "cartId": "string", "cartProducts": [{"storeProductId": "...", "productVariantId": "...", "mrp": "...", "quantity": "...", "isDiscountApplicable": "...", "isAddedToGiftBag": "..."}], "cartProductsV2": [{"storeProductId": "...", "productVariantId": "...", "mrp": "...", "quantity`
- response keys: `"JSON (truncated by capture body limit)"`

## catalogue

### `POST /cfs/api/v1/bulk-widget-data`

- host: `bff-gateway.zepto.com`
- calls observed: 7
- status codes: 200×7
- query params: -
- auth indicators: app request signature, csrf secret header, csrf token header, session header
- request body keys: `{"widgets": [{"id": "...", "pageIdentifier": "...", "widgetDisplayType": "..."}], "cartProducts": [], "enrichCall": "bool", "showAllOffers": "bool", "campaignIds": [], "couponIds": [], "alreadyShownNudgeThresholdsV2": [], "availedCampaignProducts": [], "removedCampaigns": [], "cartId": "string"}`
- response keys: `{"pageLayout": {"widgets": ["..."], "pageMeta": {"dynamicWidgetType": "...", "deliveryFeeMov": "..."}, "endOfPage": "bool"}}`

### `GET /lms/api/v2/get_page`

- host: `bff-gateway.zepto.com`
- calls observed: 16
- status codes: 200×16
- query params: enforce_platform_type, last_widget_id, latitude, layout_id, longitude, page_size, page_type, show_new_eta_banner, tab_id, version
- auth indicators: app request signature, csrf secret header, csrf token header, session header
- response keys: `{"endOfPage": "bool", "storeServiceableResponse": {"isNightlyStore": "bool", "secondaryStoreIds": ["..."], "serviceable": "bool", "storeId": "string"}, "pageLayout": {"bottomNav": {"default": "...", "items": "..."}, "endOfPage": "bool", "experienceVariant": "string", "fnvIrlVariant": "string", "foot`

### `GET /recommendation-service/api/v1/buy-again-products`

- host: `bff-gateway.zepto.com`
- calls observed: 4
- status codes: 200×4
- query params: group_id, store_id
- auth indicators: app request signature, csrf secret header, csrf token header, session header
- response keys: `{"storeProducts": [{"objectId": "...", "id": "...", "storeId": "...", "product": "...", "productVariant": "...", "discountedSellingPrice": "...", "discountPercent": "...", "discountAmount": "...", "storeProductDiscountId": "...", "availableQuantity": "...", "quantity": "...", "allocatedQuantity": ".`

## marketing

### `GET /proxy/connect.facebook.net/en_US/fbevents.js`

- host: `www.zepto.com`
- calls observed: 9
- status codes: 200×9
- query params: -
- auth indicators: none seen
- response keys: `"non-JSON body"`

### `GET /proxy/connect.facebook.net/signals/config/{n}`

- host: `www.zepto.com`
- calls observed: 9
- status codes: 200×9
- query params: domain, ex_m, hme, r, v
- auth indicators: none seen
- response keys: `"non-JSON body"`

### `GET /proxy/googleads.g.doubleclick.net/pagead/viewthroughconversion/{n}/`

- host: `www.zepto.com`
- calls observed: 1
- status codes: 200×1
- query params: _tu, async, auid, bg, cv, data, dma, en, ept, fmt, frm, fst, gcd, gtm, guid, hn, npa, pscdl, random, rcb, rfmt, tag_exp, tiba, u_h, u_w, uaa, uab, uafvl, uam, uamb, uap, uapv, uaw, url
- auth indicators: none seen

### `POST /~partytown/proxytown`

- host: `www.zepto.com`
- calls observed: 4879
- status codes: 200×4879
- query params: -
- auth indicators: none seen
- request body keys: `{"F": "string", "Q": [{"V": "...", "w": "...", "a": "..."}]}`
- response keys: `{"F": "string", "M": ["number"]}`

## orders

### `GET /api/v2/order/`

- host: `bff-gateway.zepto.com`
- calls observed: 1
- status codes: 200×1
- query params: -
- auth indicators: app request signature, csrf secret header, csrf token header, session header
- response keys: `{"orders": [{"id": "...", "code": "...", "status": "...", "formattedStatus": "...", "paymentStatus": "...", "itemQuantityCount": "...", "grandTotalAmount": "...", "totalRefundAmount": "...", "placedTime": "...", "rating": "...", "ratingSkipped": "...", "totalDeliveryTimeInSeconds": "..."}], "endOfLi`

### `GET /post-order-service/api/v2/order/last-ongoing-order`

- host: `bff-gateway.zepto.com`
- calls observed: 3
- status codes: 200×3
- query params: -
- auth indicators: app request signature, csrf secret header, csrf token header, session header
- response keys: `{"backgroundColor": "string", "bannerType": "null", "carouselBackgroundColor": "string", "carouselItemColor": "string", "carouselTextColor": "string", "img": "string", "ongoingOrders": [], "orderId": "null", "orderPlacedAt": "null", "orderStatus": "string", "subtitle": "string", "textColor": "string`

### `POST /samiksha-service/api/v1/order-rating`

- host: `bff-gateway.zepto.com`
- calls observed: 3
- status codes: 200×3
- query params: -
- auth indicators: app request signature, csrf secret header, csrf token header, session header
- request body keys: `{"order_id": "string"}`
- response keys: `{"isUserInExperiment": "bool", "isRatingSkipped": "bool", "productRatingLayoutConfig": {"isImageEnabled": "bool", "isPillEnabled": "bool", "uiConfig": {"isProfileReviewAndEarn": "...", "isReviewAndEarn": "...", "orderRatingDesign": "...", "stripPosition": "..."}}, "hygieneFeedback": {"acknowledgment`

## other

### `GET /`

- host: `www.zepto.com`
- calls observed: 2
- status codes: 200×2
- query params: _rsc
- auth indicators: none seen
- response keys: `"non-JSON body"`

### `POST /api/v1/gateway/graphql/`

- host: `bff-gateway.zepto.com`
- calls observed: 6
- status codes: 200×6
- query params: -
- auth indicators: app request signature, csrf secret header, csrf token header, session header
- request body keys: `{"operationName": "string", "variables": {}, "query": "string"}`
- response keys: `{"data": {"app": "null", "user": {"info": "...", "address": "..."}}, "errors": "null"}`

### `POST /ccm/collect`

- host: `www.google.com`
- calls observed: 1
- status codes: 200×1
- query params: _gsid, _tu, ae, apvc, auid, dl, dma, dt, en, fmt, frm, gcd, gtm, navt, npa, rcb, rnd, scrsrc, tag_exp, tfd, tft, tid, tids
- auth indicators: none seen

### `POST /measurement/conversion`

- host: `www.google.com`
- calls observed: 2
- status codes: 200×2
- query params: ae, auid, cv, dma, en, fmt, frm, fst, gacid, gcd, gtm, hn, npa, pscdl, random, rcb, ref, tag_exp, tiba, tid, u_h, u_w, uaa, uab, uafvl, uam, uamb, uap, uapv, uaw, url
- auth indicators: none seen

### `POST /payment-service/payment-listing-api/v1/quickpay`

- host: `bff-gateway.zepto.com`
- calls observed: 1
- status codes: 200×1
- query params: -
- auth indicators: app request signature
- request body keys: `{"installedUpiApps": [], "sourceId": "string", "source": "string", "isCredPayEligible": "bool", "sourceToken": "string", "ptpActionType": "string"}`
- response keys: `{"errors": [], "data": "null"}`

### `POST /rmkt/collect/{n}/`

- host: `www.google.com`
- calls observed: 1
- status codes: 200×1
- query params: _tu, async, auid, bg, cv, data, dma, en, ept, fmt, frm, fst, gcd, gcp, gtm, guid, hn, npa, pscdl, random, rcb, tag_exp, tiba, u_h, u_w, uaa, uab, uafvl, uam, uamb, uap, uapv, uaw, url
- auth indicators: none seen

### `GET /serviceability-service/api/v1/serviceability`

- host: `bff-gateway.zepto.com`
- calls observed: 1
- status codes: 200×1
- query params: lat, long
- auth indicators: app request signature, csrf secret header, csrf token header, session header
- response keys: `{"errors": [], "data": {"serviceable": "bool", "addressesData": "null", "stores": ["..."], "regionCoordinates": "null", "primary_store_meta": {"eta_delta_threshold_in_mins": "..."}}}`

### `GET /tr/`

- host: `www.facebook.com`
- calls observed: 5
- status codes: 200×5
- query params: aems, coo, dl, ec, ev, expv2[0], expv2[10], expv2[11], expv2[12], expv2[13], expv2[1], expv2[2], expv2[3], expv2[4], expv2[5], expv2[6], expv2[7], expv2[8], expv2[9], fbp, id, if, it, iw, ler, o, plt, pmd[description], pmd[keywords], pmd[locale], pmd[title], r, rl, rqm, sh, sw, ts, tz, v
- auth indicators: none seen

## search

### `GET /search-federator-service/api/v1/search`

- host: `bff-gateway.zepto.com`
- calls observed: 2
- status codes: 200×2
- query params: mode, pageNumber, query
- auth indicators: app request signature, csrf secret header, csrf token header, explicit no-bearer opt-out, session header

### `POST /user-search-service/api/v3/search/filters`

- host: `bff-gateway.zepto.com`
- calls observed: 1
- status codes: 200×1
- query params: -
- auth indicators: app request signature, csrf secret header, csrf token header, explicit no-bearer opt-out, session header
- request body keys: `{"query": "string", "mode": "string", "userSessionId": "string", "pageNumber": "number"}`
