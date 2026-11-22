/* Zepto Premium Multi-Account Shopping Platform Application */
const { useState, useEffect, useMemo, createContext, useContext } = React;

// --- Helpers to normalize Zepto-shaped payloads into the app's simple shapes ---
function toImageUrl(path) {
  if (!path) return "";
  if (path.startsWith("http")) return path;
  return `https://cdn.zeptonow.com/production/ik-seo/tr:w-600,cm-pad_resize/${path}`;
}

function toSimpleProduct(sp) {
  if (!sp) return null;
  const variant = sp.productVariant || {};
  const image = (variant.images && variant.images[0]) || {};
  return {
    id: sp.id,
    name: sp.product ? sp.product.name : sp.name,
    brand: sp.product ? sp.product.brand : sp.brand,
    category: sp.category || (sp.product && sp.product.l3CategoryDetails && sp.product.l3CategoryDetails.name),
    price: (sp.discountedSellingPrice || sp.price || 0) / (sp.discountedSellingPrice ? 100 : 1),
    originalPrice: (sp.mrp || sp.originalPrice || 0) / (sp.mrp ? 100 : 1),
    discountPercent: sp.discountPercent || 0,
    unit: variant.formattedPacksize || sp.unit,
    imageUrl: toImageUrl(image.path || sp.imageUrl),
    rating: variant.rating || sp.rating,
    availability: sp.isAvailable != null ? sp.isAvailable : (sp.availability != null ? sp.availability : true),
  };
}

function toSimpleCart(c) {
  if (!c) return { itemCount: 0, items: [], cartTotal: 0, deliveryFee: 0, finalPayable: 0 };
  const items = (c.cartProducts || []).map(sp => ({
    id: sp.cartProductId || sp.id,
    productId: sp.id,
    name: sp.product ? sp.product.name : sp.name,
    brand: sp.product ? sp.product.brand : sp.brand,
    unit: (sp.productVariant && sp.productVariant.formattedPacksize) || sp.unit,
    price: (sp.discountedSellingPrice || 0) / 100,
    originalPrice: (sp.mrp || 0) / 100,
    discountPercent: sp.discountPercent || 0,
    quantity: sp.quantity || 1,
    imageUrl: toImageUrl((sp.productVariant && sp.productVariant.images && sp.productVariant.images[0] && sp.productVariant.images[0].path) || sp.imageUrl),
    total: (sp.lineTotal || 0) / 100,
  }));
  const applied = c.appliedCoupon || c.applied || null;
  return {
    cartId: c.cartId,
    itemCount: c.cartItemCount != null ? c.cartItemCount : (c.itemsCount || 0),
    items,
    mrpTotal: (c.totalMrp || 0) / 100,
    itemDiscount: (c.totalDiscount || 0) / 100,
    cartTotal: (c.totalSellingPrice || 0) / 100,
    deliveryFee: (c.deliveryFee || 0) / 100,
    freeDeliveryThreshold: (c.freeDeliveryThreshold || 0) / 100,
    amountNeededForFreeDelivery: (c.deliveryFeeMov || 0) / 100,
    finalPayable: (c.totalPayable || 0) / 100,
    appliedCoupon: applied ? { code: applied.code, title: applied.title, discountAmount: (c.couponDiscount || 0) / 100 } : null,
  };
}

// --- API Service Client ---
const API = {
  token: localStorage.getItem("zepto_token") || "",
  activeAccountId: localStorage.getItem("zepto_account_id") || "",

  getHeaders() {
    const headers = { "Content-Type": "application/json" };
    const initData = window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData;
    if (initData) headers["X-Telegram-Init-Data"] = initData;
    if (this.activeAccountId) headers["X-Account-Id"] = this.activeAccountId;
    if (this.token) headers["Authorization"] = `Bearer ${this.token}`;
    return headers;
  },

  async request(path, options = {}) {
    const headers = { ...this.getHeaders(), ...(options.headers || {}) };
    const res = await fetch(path, { ...options, headers });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Request failed" }));
      throw new Error(err.detail || err.error || "Error connecting to server");
    }
    return res.json();
  },

  async ensureAuth() {
    if (this.token) return this.token;
    await this.request("/api/v1/user/customer/send-otp-sms/", { method: "POST", body: JSON.stringify({ mobileNumber: "9876542168" }) });
    const res = await this.request("/api/auth/verify-otp", { method: "POST", body: JSON.stringify({ mobileNumber: "9876542168", otpToken: "123456", fullName: "Zepto Shopper" }) });
    this.token = res.sessionToken;
    localStorage.setItem("zepto_token", this.token);
    return this.token;
  },

  // Accounts (still simple backend)
  getAccounts() { return this.request("/api/accounts"); },
  switchAccount(accountId) { return this.request("/api/accounts/switch", { method: "POST", body: JSON.stringify({ account_id: accountId }) }); },
  addAccount(mobile, name) { return this.request("/api/accounts/add", { method: "POST", body: JSON.stringify({ mobile_number: mobile, display_name: name }) }); },
  renameAccount(id, name) { return this.request(`/api/accounts/${id}/rename`, { method: "PUT", body: JSON.stringify({ display_name: name }) }); },
  deleteAccount(id) { return this.request(`/api/accounts/${id}`, { method: "DELETE" }); },

  // Catalogue (Zepto-shaped)
  async getHomeLayout() {
    await this.ensureAuth();
    const res = await this.request("/lms/api/v2/get_page?page_type=HOME&page_size=30");
    if (res.pageLayout && res.pageLayout.widgets) {
      res.pageLayout.widgets = res.pageLayout.widgets.map(w => {
        if (w.widgetType === "CATEGORY_GRID" && w.data && Array.isArray(w.data.categories)) {
          w.data.categories = w.data.categories.map(c => (c && c.name) ? c.name : c);
          w.categories = w.data.categories;
        }
        if (w.data && Array.isArray(w.data.storeProducts)) {
          const sps = w.data.storeProducts.map(toSimpleProduct);
          w.data.storeProducts = sps;
          w.products = sps;
        }
        return w;
      });
    }
    return res;
  },
  getProductDetail(id) { return this.request(`/api/products/${id}`); },
  async search(q, category, sortBy) {
    await this.ensureAuth();
    const filters = {};
    if (category && category !== "All") filters.category = category;
    if (sortBy) filters.sortBy = sortBy;
    const res = await this.request("/user-search-service/api/v3/search", { method: "POST", body: JSON.stringify({ query: q || "", pageNumber: 0, filters }) });
    const products = (res.products || res.storeProducts || []).map(toSimpleProduct);
    return { items: products, facets: res.facets || { categories: res.filters ? res.filters.map(f=>f.id) : [], brands: [] } };
  },

  // Cart (Zepto-shaped)
  async getCart() {
    await this.ensureAuth();
    const res = await this.request("/cfs/api/v1/cart");
    return toSimpleCart(res);
  },
  async addToCart(productId, quantity = 1) {
    await this.ensureAuth();
    const res = await this.request("/cfs/api/v1/cart/add", { method: "POST", body: JSON.stringify({ storeProductId: productId, quantity }) });
    return toSimpleCart(res);
  },
  async updateCart(productId, quantity) {
    await this.ensureAuth();
    const res = await this.request("/cfs/api/v1/cart/update", { method: "POST", body: JSON.stringify({ storeProductId: productId, quantity }) });
    return toSimpleCart(res);
  },
  async clearCart() {
    await this.ensureAuth();
    const res = await this.request("/cfs/api/v1/cart/clear", { method: "POST" });
    return toSimpleCart(res);
  },

  // Offers / Coupons (Zepto-shaped)
  async getOffers() {
    await this.ensureAuth();
    const res = await this.request("/coupon-service/api/v1/coupons");
    const raw = res.coupons || [];
    const coupons = raw.map(cp => ({
      id: cp.id || cp.couponId,
      code: cp.code,
      title: cp.title,
      description: cp.description,
      isEligible: cp.isEligible,
      amountNeeded: (cp.amountNeeded || 0) / 100,
    }));
    const eligible = raw.filter(c => c.isEligible).sort((a, b) => (b.potentialDiscount || 0) - (a.potentialDiscount || 0));
    const best = eligible[0];
    const evaluation = {
      hasEligibleOffer: eligible.length > 0,
      recommendedOffer: best ? { code: best.code, discountAmount: (best.potentialDiscount || 0) / 100 } : null,
    };
    return { evaluation, availableOffers: coupons };
  },
  async autoApplyBestOffer() {
    await this.ensureAuth();
    const res = await this.request("/coupon-service/api/v1/coupons");
    const raw = res.coupons || [];
    const best = raw.filter(c => c.isEligible).sort((a, b) => (b.potentialDiscount || 0) - (a.potentialDiscount || 0))[0];
    if (!best) throw new Error("No eligible offer");
    const appliedRes = await this.request("/coupon-service/api/v1/coupons/apply", { method: "POST", body: JSON.stringify({ code: best.code }) });
    const applied = appliedRes.appliedCoupon || appliedRes.applied || {};
    return { success: true, appliedOffer: { code: applied.code || best.code, discountAmount: (appliedRes.couponDiscount || 0) / 100 } };
  },
  async validateCoupon(code) {
    await this.ensureAuth();
    const res = await this.request("/coupon-service/api/v1/coupons/apply", { method: "POST", body: JSON.stringify({ code }) });
    const applied = res.appliedCoupon || res.applied || {};
    return { code: applied.code || code, discount: (res.couponDiscount || 0) / 100, title: applied.title };
  },

  getCheckoutSummary(couponCode, addressId) {
    return Promise.resolve({ valid: true });
  },
  async placeOrder(paymentMethod, addressId, couponCode) {
    await this.ensureAuth();
    const res = await this.request("/order-service/api/v1/orders/create", { method: "POST", body: JSON.stringify({ paymentMethod, addressId }) });
    return { success: true, order: res.order };
  },
  async getOrders() {
    await this.ensureAuth();
    const res = await this.request("/api/v2/order/");
    const orders = (res.orders || []).map(o => ({
      id: o.id,
      orderCode: o.code,
      status: o.status,
      totalAmount: (o.grandTotalAmount || 0) / 100,
      items: (o.productsNamesAndCounts || []).map(p => ({ name: p.name, quantity: p.count, total: 0 })),
      etaMinutes: o.etaMinutes || 10,
      placedAt: o.placedTime,
    }));
    return { orders };
  },
  getOrderDetails(id) { return this.request(`/api/orders/${id}`); },
  getLiveTracking(id) { return this.request(`/api/delivery/track/${id}`); },

  async getProfile() {
    await this.ensureAuth();
    const res = await this.request("/api/v2/user/customer/info/", { method: "POST", body: JSON.stringify({}) });
    return { profile: res, pass: {}, wallet: {}, referral: {} };
  },
  async getAddresses() {
    await this.ensureAuth();
    const res = await this.request("/api/v1/user/customer/addresses/");
    const list = res.addresses || [];
    return { addresses: list.map(a => ({ id: a.id, type: a.type || "HOME", label: a.name || a.type || "Address", ...a })) };
  },
  getFaqs() { return this.request("/api/support/faqs"); },

  exportAccounts() { return this.request("/api/backup/export"); },
  previewImport(payload) { return this.request("/api/backup/preview", { method: "POST", body: JSON.stringify(payload) }); },
  confirmImport(payload) { return this.request("/api/backup/import", { method: "POST", body: JSON.stringify(payload) }); },
};

// --- App Context ---
const AppContext = createContext(null);

function AppProvider({ children }) {
  const [currentView, setCurrentView] = useState("home");
  const [viewParam, setViewParam] = useState(null);
  const [darkMode, setDarkMode] = useState(false);
  const [accounts, setAccounts] = useState([]);
  const [activeAccount, setActiveAccount] = useState(null);
  const [cart, setCart] = useState({ itemCount: 0, items: [], cartTotal: 0, deliveryFee: 0, finalPayable: 0 });
  const [isAccountModalOpen, setIsAccountModalOpen] = useState(false);
  const [toasts, setToasts] = useState([]);
  const [activeCoupon, setActiveCoupon] = useState(null);

  const showToast = (message, type = "success") => {
    const id = Date.now();
    setToasts(prev => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, 3200);
  };

  const navigate = (view, param = null) => {
    setCurrentView(view);
    setViewParam(param);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  // Load Accounts
  const refreshAccounts = async () => {
    try {
      const data = await API.getAccounts();
      setAccounts(data.accounts || []);
      const active = data.accounts.find(a => a.accountId === data.activeAccountId) || data.accounts[0];
      setActiveAccount(active);
      if (active) {
        API.activeAccountId = active.accountId;
        localStorage.setItem("zepto_account_id", active.accountId);
      }
    } catch (err) {
      console.error("Accounts error:", err);
    }
  };

  // Load Cart
  const refreshCart = async () => {
    try {
      const cartData = await API.getCart();
      setCart(cartData);
    } catch (err) {
      console.error("Cart error:", err);
    }
  };

  useEffect(() => {
    refreshAccounts();
  }, []);

  useEffect(() => {
    if (activeAccount) {
      refreshCart();
    }
  }, [activeAccount?.accountId]);

  // Handle Switch
  const switchAccount = async (accId) => {
    try {
      await API.switchAccount(accId);
      API.activeAccountId = accId;
      localStorage.setItem("zepto_account_id", accId);
      const acc = accounts.find(a => a.accountId === accId);
      setActiveAccount(acc);
      setActiveCoupon(null);
      await refreshCart();
      showToast(`Switched to ${acc?.displayName || "Account"}!`);
      setIsAccountModalOpen(false);
    } catch (err) {
      showToast(err.message, "error");
    }
  };

  // Add Item Helper
  const addItem = async (productId, qty = 1) => {
    try {
      const updated = await API.addToCart(productId, qty);
      setCart(updated);
      showToast("Item added to cart! 🛒");
    } catch (err) {
      showToast(err.message, "error");
    }
  };

  const updateItemQty = async (productId, qty) => {
    try {
      const updated = await API.updateCart(productId, qty);
      setCart(updated);
    } catch (err) {
      showToast(err.message, "error");
    }
  };

  const value = {
    currentView,
    viewParam,
    navigate,
    darkMode,
    setDarkMode,
    accounts,
    activeAccount,
    switchAccount,
    refreshAccounts,
    cart,
    refreshCart,
    addItem,
    updateItemQty,
    isAccountModalOpen,
    setIsAccountModalOpen,
    toasts,
    showToast,
    activeCoupon,
    setActiveCoupon,
  };

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

const useApp = () => useContext(AppContext);

// --- Header Component ---
function Header() {
  const { navigate, darkMode, setDarkMode, activeAccount, setIsAccountModalOpen, cart } = useApp();
  const [searchQuery, setSearchQuery] = useState("");
  const [deliveryLabel, setDeliveryLabel] = useState("Locating…");
  const [addresses, setAddresses] = useState([]);
  const [addressOpen, setAddressOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    API.getAddresses()
      .then(res => {
        if (cancelled) return;
        const list = res.addresses || [];
        setAddresses(list);
        const saved = localStorage.getItem("zepto_address_id");
        const chosen = list.find(a => a.id === saved) || list.find(a => a.isDefault) || list[0];
        setDeliveryLabel(chosen ? chosen.label : "No saved address");
      })
      .catch(() => {
        if (!cancelled) setDeliveryLabel("Address unavailable");
      });
    return () => { cancelled = true; };
  }, [activeAccount?.accountId]);

  const pickAddress = (address) => {
    setDeliveryLabel(address.label);
    localStorage.setItem("zepto_address_id", address.id);
    setAddressOpen(false);
  };

  const handleSearch = (e) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      navigate("search", searchQuery.trim());
    }
  };

  return (
    <header className="sticky top-0 z-40 bg-white/90 dark:bg-slate-900/90 backdrop-blur-md border-b border-slate-200 dark:border-slate-800 transition-colors">
      <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between gap-3">
        {/* Logo & Delivery ETA */}
        <div className="flex items-center gap-3 cursor-pointer" onClick={() => navigate("home")}>
          <div className="flex items-center gap-2">
            <div className="w-10 h-10 rounded-2xl bg-gradient-to-tr from-indigo-700 via-indigo-600 to-violet-500 flex items-center justify-center text-white font-black text-xl shadow-md shadow-indigo-500/20">
              ⚡
            </div>
            <div>
              <div className="flex items-center gap-1.5">
                <span className="font-extrabold text-xl tracking-tight text-slate-900 dark:text-white">zepto</span>
                <span className="px-1.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-400">10m</span>
              </div>
              <div className="relative">
                <button
                  type="button"
                  onClick={(e) => { e.stopPropagation(); setAddressOpen(open => !open); }}
                  className="text-xs text-slate-500 dark:text-slate-400 flex items-center gap-1 max-w-[260px] hover:text-indigo-600 dark:hover:text-indigo-400 transition"
                  aria-haspopup="listbox"
                  aria-expanded={addressOpen}
                >
                  <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse flex-shrink-0"></span>
                  <span className="truncate" title={deliveryLabel}>{deliveryLabel}</span>
                  {addresses.length > 1 && <span className="text-[10px] opacity-70">▾</span>}
                </button>

                {addressOpen && addresses.length > 0 && (
                  <div
                    role="listbox"
                    className="absolute left-0 top-6 z-50 w-80 max-h-72 overflow-y-auto rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-xl p-1.5 space-y-1"
                  >
                    {addresses.map(address => {
                      const selected = address.label === deliveryLabel;
                      return (
                        <button
                          key={address.id}
                          type="button"
                          role="option"
                          aria-selected={selected}
                          onClick={(e) => { e.stopPropagation(); pickAddress(address); }}
                          className={`w-full text-left px-3 py-2 rounded-xl transition ${selected ? "bg-indigo-50 dark:bg-indigo-950/60" : "hover:bg-slate-100 dark:hover:bg-slate-800"}`}
                        >
                          <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                            {address.type || "HOME"}
                          </div>
                          <div className="text-xs font-semibold text-slate-700 dark:text-slate-200 leading-snug">
                            {address.label}
                          </div>
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Search Bar (Desktop) */}
        <form onSubmit={handleSearch} className="hidden md:flex flex-1 max-w-xl mx-4">
          <div className="relative w-full">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search for 'milk', 'mango', 'chocolate', 'chips'..."
              className="w-full pl-10 pr-4 py-2.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 border border-transparent focus:border-indigo-400 transition"
            />
            <span className="absolute left-3.5 top-2.5 text-slate-400">🔍</span>
          </div>
        </form>

        {/* Right Controls */}
        <div className="flex items-center gap-2.5">
          {/* Account Switcher Pill */}
          <button
            onClick={() => setIsAccountModalOpen(true)}
            className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-800 dark:text-slate-200 text-xs font-semibold border border-slate-200 dark:border-slate-700 transition"
          >
            <div className="w-5 h-5 rounded-full bg-indigo-600 text-white flex items-center justify-center text-[10px] font-bold">
              👤
            </div>
            <div className="text-left hidden sm:block">
              <div className="truncate max-w-[110px]">{activeAccount?.displayName || "Account"}</div>
            </div>
            <span className="text-slate-400 text-xs">▼</span>
          </button>

          {/* Theme Toggle */}
          <button
            onClick={() => {
              setDarkMode(!darkMode);
              document.body.classList.toggle("dark-mode", !darkMode);
              document.documentElement.classList.toggle("dark", !darkMode);
            }}
            className="w-9 h-9 rounded-full flex items-center justify-center bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-600 dark:text-slate-300 transition"
          >
            {darkMode ? "☀️" : "🌙"}
          </button>

          {/* Cart Button */}
          <button
            onClick={() => navigate("cart")}
            className="flex items-center gap-2 px-4 py-2 rounded-full bg-gradient-to-r from-emerald-600 to-emerald-500 hover:from-emerald-700 hover:to-emerald-600 text-white font-bold text-xs shadow-md shadow-emerald-500/20 transition"
          >
            <span>🛒</span>
            <span>₹{cart.cartTotal}</span>
            {cart.itemCount > 0 && (
              <span className="px-1.5 py-0.2 rounded-full bg-white text-emerald-800 text-[11px] font-extrabold">
                {cart.itemCount}
              </span>
            )}
          </button>
        </div>
      </div>
    </header>
  );
}

// --- Mobile Bottom Navigation ---
function BottomNav() {
  const { currentView, navigate, cart, setIsAccountModalOpen } = useApp();

  const navItems = [
    { id: "home", label: "Home", icon: "🏠" },
    { id: "categories", label: "Browse", icon: "🛍️" },
    { id: "offers", label: "Offers", icon: "⚡" },
    { id: "cart", label: "Cart", icon: "🛒", badge: cart.itemCount },
    { id: "accounts", label: "Accounts", icon: "👥" },
  ];

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-40 bg-white/95 dark:bg-slate-900/95 backdrop-blur-lg border-t border-slate-200 dark:border-slate-800 md:hidden transition-colors">
      <div className="grid grid-cols-5 py-1">
        {navItems.map((item) => {
          const isActive = currentView === item.id;
          return (
            <button
              key={item.id}
              onClick={() => {
                if (item.id === "accounts") {
                  setIsAccountModalOpen(true);
                } else {
                  navigate(item.id);
                }
              }}
              className={`flex flex-col items-center justify-center py-1.5 relative ${
                isActive ? "text-indigo-600 dark:text-indigo-400 font-bold" : "text-slate-500 dark:text-slate-400 font-medium"
              }`}
            >
              <div className="text-lg relative">
                {item.icon}
                {item.badge > 0 && (
                  <span className="absolute -top-1 -right-2 px-1 py-0.2 min-w-[16px] h-4 rounded-full bg-emerald-600 text-white text-[9px] font-bold flex items-center justify-center">
                    {item.badge}
                  </span>
                )}
              </div>
              <span className="text-[10px] mt-0.5">{item.label}</span>
            </button>
          );
        })}
      </div>
    </nav>
  );
}

// --- Account Switcher Bottom Sheet / Modal ---
function AccountModal() {
  const { isAccountModalOpen, setIsAccountModalOpen, accounts, activeAccount, switchAccount, refreshAccounts, showToast, navigate } = useApp();
  const [showAddForm, setShowAddForm] = useState(false);
  const [newMobile, setNewMobile] = useState("");
  const [newName, setNewName] = useState("");

  if (!isAccountModalOpen) return null;

  const handleAdd = async (e) => {
    e.preventDefault();
    if (!newMobile || newMobile.length < 10) {
      showToast("Please enter a valid 10-digit number", "error");
      return;
    }
    try {
      await API.addAccount(newMobile, newName || `Account (${newMobile.slice(-4)})`);
      showToast("Account added successfully! 🎉");
      setShowAddForm(false);
      setNewMobile("");
      setNewName("");
      await refreshAccounts();
    } catch (err) {
      showToast(err.message, "error");
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/60 backdrop-blur-sm p-0 sm:p-4 transition-all">
      <div className="bg-white dark:bg-slate-900 rounded-t-3xl sm:rounded-3xl w-full max-w-md max-h-[85vh] flex flex-col shadow-2xl border border-slate-200 dark:border-slate-800 overflow-hidden">
        {/* Modal Header */}
        <div className="p-5 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-full bg-indigo-100 dark:bg-indigo-950 text-indigo-600 dark:text-indigo-400 flex items-center justify-center font-bold">
              👥
            </div>
            <div>
              <h3 className="font-extrabold text-slate-900 dark:text-white text-base">Multi-Account Switcher</h3>
              <p className="text-xs text-slate-500">Isolated carts, addresses & eligibility</p>
            </div>
          </div>
          <button
            onClick={() => setIsAccountModalOpen(false)}
            className="w-8 h-8 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 flex items-center justify-center"
          >
            ✕
          </button>
        </div>

        {/* Account List */}
        <div className="p-5 overflow-y-auto space-y-3 flex-1">
          {accounts.map((acc) => {
            const isActive = acc.accountId === activeAccount?.accountId;
            return (
              <div
                key={acc.accountId}
                onClick={() => switchAccount(acc.accountId)}
                className={`p-3.5 rounded-2xl border cursor-pointer transition flex items-center justify-between ${
                  isActive
                    ? "bg-indigo-50/70 dark:bg-indigo-950/40 border-indigo-500 ring-2 ring-indigo-500/20"
                    : "bg-slate-50 dark:bg-slate-800/50 border-slate-200 dark:border-slate-700/60 hover:border-slate-300"
                }`}
              >
                <div className="flex items-center gap-3">
                  <div className={`w-10 h-10 rounded-xl flex items-center justify-center font-bold text-sm ${
                    isActive ? "bg-indigo-600 text-white" : "bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-200"
                  }`}>
                    {acc.displayName.slice(0, 2).toUpperCase()}
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-sm text-slate-900 dark:text-slate-100">{acc.displayName}</span>
                      {acc.isDefault && (
                        <span className="px-1.5 py-0.2 rounded text-[10px] font-semibold bg-slate-200 dark:bg-slate-700 text-slate-600 dark:text-slate-300">
                          Default
                        </span>
                      )}
                    </div>
                    <div className="text-xs text-slate-500 font-mono mt-0.5">{acc.maskedMobile}</div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {isActive ? (
                    <span className="px-2.5 py-1 rounded-full bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-400 text-xs font-bold flex items-center gap-1">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span> Active
                    </span>
                  ) : (
                    <span className="text-xs text-indigo-600 dark:text-indigo-400 font-semibold hover:underline">
                      Switch
                    </span>
                  )}
                </div>
              </div>
            );
          })}

          {showAddForm ? (
            <form onSubmit={handleAdd} className="mt-4 p-4 rounded-2xl bg-slate-100 dark:bg-slate-800 space-y-3">
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-600 dark:text-slate-300">Add Another Shopping Account</h4>
              <input
                type="text"
                placeholder="10-digit mobile number"
                value={newMobile}
                onChange={(e) => setNewMobile(e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
              <input
                type="text"
                placeholder="Account display name (e.g. Work, Family)"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
              <div className="flex gap-2">
                <button
                  type="submit"
                  className="flex-1 py-2 rounded-xl bg-indigo-600 text-white font-bold text-xs hover:bg-indigo-700 transition"
                >
                  Verify & Link Account
                </button>
                <button
                  type="button"
                  onClick={() => setShowAddForm(false)}
                  className="px-4 py-2 rounded-xl bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-300 text-xs font-semibold"
                >
                  Cancel
                </button>
              </div>
            </form>
          ) : (
            <button
              onClick={() => setShowAddForm(true)}
              className="w-full py-3 rounded-2xl border-2 border-dashed border-slate-300 dark:border-slate-700 text-indigo-600 dark:text-indigo-400 hover:border-indigo-400 font-bold text-xs flex items-center justify-center gap-2 transition"
            >
              <span>➕</span> Add New Shopping Account
            </button>
          )}
        </div>

        {/* Modal Footer (Import / Export Link) */}
        <div className="p-4 bg-slate-50 dark:bg-slate-800/80 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between text-xs">
          <span className="text-slate-500">Need backup?</span>
          <button
            onClick={() => {
              setIsAccountModalOpen(false);
              navigate("backup");
            }}
            className="text-indigo-600 dark:text-indigo-400 font-bold hover:underline"
          >
            Export / Import JSON ➔
          </button>
        </div>
      </div>
    </div>
  );
}

// --- Product Card Component ---
function ProductCard({ product }) {
  const { cart, addItem, updateItemQty, navigate } = useApp();
  const [isWishlisted, setIsWishlisted] = useState(false);

  const cartItem = cart.items.find(it => it.productId === product.id);
  const qty = cartItem ? cartItem.quantity : 0;

  return (
    <div className="group relative bg-white dark:bg-slate-900 rounded-3xl p-3.5 border border-slate-200/80 dark:border-slate-800 shadow-sm hover:shadow-xl hover:-translate-y-1 transition duration-300 flex flex-col justify-between">
      {/* Top badges */}
      <div className="flex items-center justify-between mb-2">
        {product.discountPercent > 0 ? (
          <span className="px-2 py-0.5 rounded-full bg-emerald-600 text-white font-extrabold text-[10px] tracking-wider uppercase shadow-sm">
            {product.discountPercent}% OFF
          </span>
        ) : (
          <span className="px-2 py-0.5 rounded-full bg-indigo-50 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-300 font-semibold text-[10px]">
            ⚡ 10m
          </span>
        )}
        <button
          onClick={(e) => {
            e.stopPropagation();
            setIsWishlisted(!isWishlisted);
          }}
          className="w-7 h-7 rounded-full bg-slate-100 dark:bg-slate-800 flex items-center justify-center text-xs hover:scale-110 transition"
        >
          {isWishlisted ? "❤️" : "🤍"}
        </button>
      </div>

      {/* Image */}
      <div
        className="w-full h-36 rounded-2xl overflow-hidden bg-slate-50 dark:bg-slate-800 flex items-center justify-center p-2 mb-3 cursor-pointer"
        onClick={() => navigate("product", product.id)}
      >
        <img
          src={product.imageUrl || product.image_url}
          alt={product.name}
          className="max-h-full max-w-full object-contain group-hover:scale-105 transition duration-300"
          loading="lazy"
        />
      </div>

      {/* Content */}
      <div className="flex-1 cursor-pointer" onClick={() => navigate("product", product.id)}>
        <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">{product.brand || "Zepto Fresh"}</div>
        <h4 className="font-bold text-slate-900 dark:text-white text-sm line-clamp-2 mt-0.5 group-hover:text-indigo-600 dark:group-hover:text-indigo-400 transition">
          {product.name}
        </h4>
        <div className="text-xs text-slate-500 mt-1">{product.unit}</div>
      </div>

      {/* Pricing & Add Stepper */}
      <div className="mt-3 pt-3 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between">
        <div>
          <div className="flex items-baseline gap-1.5">
            <span className="font-extrabold text-base text-slate-900 dark:text-white">₹{product.price}</span>
            {product.originalPrice > product.price && (
              <span className="text-xs text-slate-400 line-through">₹{product.originalPrice}</span>
            )}
          </div>
        </div>

        {qty > 0 ? (
          <div className="flex items-center bg-indigo-600 rounded-xl text-white font-bold text-xs overflow-hidden shadow-md">
            <button
              onClick={() => updateItemQty(product.id, qty - 1)}
              className="px-2.5 py-1.5 hover:bg-indigo-700 active:scale-95 transition"
            >
              −
            </button>
            <span className="px-2 py-1.5 font-extrabold">{qty}</span>
            <button
              onClick={() => updateItemQty(product.id, qty + 1)}
              className="px-2.5 py-1.5 hover:bg-indigo-700 active:scale-95 transition"
            >
              +
            </button>
          </div>
        ) : (
          <button
            onClick={() => addItem(product.id, 1)}
            className="px-4 py-1.5 rounded-xl bg-indigo-50 dark:bg-indigo-950/60 hover:bg-indigo-600 text-indigo-700 dark:text-indigo-300 hover:text-white font-bold text-xs border border-indigo-200 dark:border-indigo-800/60 hover:border-transparent shadow-sm transition active:scale-95"
          >
            ADD
          </button>
        )}
      </div>
    </div>
  );
}

// --- Best Offer Hero Banner ---
function BestOfferBanner() {
  const { cart, navigate, showToast, refreshCart, setActiveCoupon } = useApp();
  const [evalData, setEvalData] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    API.getOffers().then(res => setEvalData(res.evaluation)).catch(console.error);
  }, [cart.cartTotal]);

  const handleAutoApply = async () => {
    setLoading(true);
    try {
      const res = await API.autoApplyBestOffer();
      if (res.success) {
        setActiveCoupon(res.appliedOffer);
        showToast(`🎉 Applied ${res.appliedOffer.code}! Saved ₹${res.appliedOffer.discountAmount}`);
        await refreshCart();
      }
    } catch (err) {
      showToast(err.message, "error");
    } finally {
      setLoading(false);
    }
  };

  const hasOffer = evalData?.hasEligibleOffer;
  const rec = evalData?.recommendedOffer;

  return (
    <div className="relative overflow-hidden rounded-3xl bg-gradient-to-r from-indigo-900 via-indigo-800 to-violet-900 text-white p-5 md:p-6 shadow-xl border border-indigo-700/50">
      <div className="relative z-10 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-violet-500/20 text-violet-200 text-xs font-bold border border-violet-400/30 mb-2">
            <span>✨</span> Intelligent Best-Offer Engine
          </div>
          <h2 className="text-xl md:text-2xl font-black tracking-tight">
            {hasOffer ? `Save ₹${rec.discountAmount} with Coupon ${rec.code}!` : "Unlock Extra Savings on Your Order"}
          </h2>
          <p className="text-xs md:text-sm text-indigo-200 mt-1 max-w-xl">
            {hasOffer
              ? `Our engine analyzed all active discounts and found the optimal offer for your cart.`
              : "Add your favorite snacks and groceries. The best eligible offer will be computed automatically."}
          </p>
        </div>

        <div className="flex items-center gap-3 w-full md:w-auto">
          {hasOffer && (
            <button
              onClick={handleAutoApply}
              disabled={loading}
              className="flex-1 md:flex-initial px-6 py-3 rounded-2xl bg-gradient-to-r from-emerald-500 to-emerald-400 hover:from-emerald-600 hover:to-emerald-500 text-slate-950 font-black text-xs md:text-sm shadow-lg shadow-emerald-500/30 hover:scale-105 active:scale-95 transition flex items-center justify-center gap-2"
            >
              <span>⚡</span> {loading ? "Evaluating..." : "AUTO APPLY BEST OFFER"}
            </button>
          )}
          <button
            onClick={() => navigate("offers")}
            className="px-4 py-3 rounded-2xl bg-white/10 hover:bg-white/20 text-white font-bold text-xs transition"
          >
            All Coupons
          </button>
        </div>
      </div>
    </div>
  );
}

// --- Home Page ---
function HomePage() {
  const { navigate } = useApp();
  const [layout, setLayout] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    API.getHomeLayout()
      .then(res => {
        setLayout(res);
        setLoading(false);
      })
      .catch(err => {
        console.error(err);
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-8 space-y-6">
        <div className="h-44 rounded-3xl skeleton-box"></div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map(n => (
            <div key={n} className="h-64 rounded-3xl skeleton-box"></div>
          ))}
        </div>
      </div>
    );
  }

  const widgets = layout?.pageLayout?.widgets || [];
  const hero = widgets.find(w => w.widgetType === "HERO_BANNER");
  const categoriesWidget = widgets.find(w => w.widgetType === "CATEGORY_GRID");
  const carousel = widgets.find(w => w.widgetType === "PRODUCT_CAROUSEL");
  const grid = widgets.find(w => w.widgetType === "PRODUCT_GRID");

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 space-y-8">
      {/* Best Offer Engine Banner */}
      <BestOfferBanner />

      {/* Hero Banner */}
      {hero && (
        <div className="relative rounded-3xl overflow-hidden bg-gradient-to-r from-violet-600 via-indigo-600 to-indigo-800 text-white p-6 md:p-8 flex items-center justify-between shadow-lg">
          <div className="max-w-md space-y-2">
            <span className="px-2.5 py-1 rounded-full bg-white/20 text-xs font-bold uppercase tracking-wider">
              Express Delivery
            </span>
            <h1 className="text-2xl md:text-3xl font-black">{hero.title}</h1>
            <p className="text-indigo-100 text-xs md:text-sm">{hero.subtitle}</p>
            <button
              onClick={() => navigate("categories")}
              className="mt-3 px-5 py-2.5 rounded-xl bg-white text-indigo-900 font-extrabold text-xs shadow-md hover:bg-indigo-50 transition"
            >
              Shop All Groceries ➔
            </button>
          </div>
          <div className="hidden lg:block text-7xl">🥦🍎🥑</div>
        </div>
      )}

      {/* Categories Horizontal Scroller */}
      {categoriesWidget && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="font-extrabold text-lg text-slate-900 dark:text-white">Explore Categories</h3>
            <button onClick={() => navigate("categories")} className="text-xs font-bold text-indigo-600 dark:text-indigo-400 hover:underline">
              See All ➔
            </button>
          </div>
          <div className="flex gap-3 overflow-x-auto pb-2 scrollbar-none">
            {categoriesWidget.categories.map((cat, i) => (
              <div
                key={i}
                onClick={() => navigate("search", cat)}
                className="flex-shrink-0 px-4 py-3 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 hover:border-indigo-400 hover:shadow-md cursor-pointer transition flex items-center gap-2.5 font-bold text-xs text-slate-800 dark:text-slate-200"
              >
                <span>✨</span>
                <span>{cat}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Trending Carousel */}
      {carousel && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-xl">🔥</span>
              <h3 className="font-extrabold text-lg text-slate-900 dark:text-white">{carousel.title}</h3>
            </div>
            <span className="text-xs text-slate-400">10m Delivery</span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3.5">
            {carousel.products.map(p => (
              <ProductCard key={p.id} product={p} />
            ))}
          </div>
        </div>
      )}

      {/* Popular Products Grid */}
      {grid && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-xl">⭐</span>
              <h3 className="font-extrabold text-lg text-slate-900 dark:text-white">{grid.title}</h3>
            </div>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
            {grid.products.map(p => (
              <ProductCard key={p.id} product={p} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// --- Search & Categories Page ---
function SearchPage() {
  const { viewParam, navigate } = useApp();
  const [query, setQuery] = useState(viewParam || "");
  const [results, setResults] = useState([]);
  const [facets, setFacets] = useState({ categories: [], brands: [] });
  const [selectedCategory, setSelectedCategory] = useState("All");
  const [sortBy, setSortBy] = useState("popular");
  const [loading, setLoading] = useState(false);

  const executeSearch = async () => {
    setLoading(true);
    try {
      const data = await API.search(query, selectedCategory, sortBy);
      setResults(data.items || []);
      setFacets(data.facets || { categories: [], brands: [] });
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    executeSearch();
  }, [query, selectedCategory, sortBy]);

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 space-y-6">
      {/* Search Bar */}
      <div className="flex flex-col md:flex-row gap-3 items-center justify-between">
        <div className="relative w-full md:max-w-xl">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search items, categories, brands..."
            className="w-full pl-10 pr-4 py-3 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
          <span className="absolute left-3.5 top-3 text-slate-400">🔍</span>
        </div>

        {/* Filters & Sorting */}
        <div className="flex items-center gap-2 w-full md:w-auto overflow-x-auto pb-1">
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            className="px-3 py-2.5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-xs font-semibold"
          >
            <option value="popular">Popularity</option>
            <option value="price_asc">Price: Low to High</option>
            <option value="price_desc">Price: High to Low</option>
            <option value="discount">Highest Discount</option>
          </select>

          <select
            value={selectedCategory}
            onChange={(e) => setSelectedCategory(e.target.value)}
            className="px-3 py-2.5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-xs font-semibold"
          >
            <option value="All">All Categories</option>
            {facets.categories.map((c, i) => (
              <option key={i} value={c}>{c}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Results Grid */}
      {loading ? (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
          {[1, 2, 3, 4, 5, 6].map(n => (
            <div key={n} className="h-64 rounded-3xl skeleton-box"></div>
          ))}
        </div>
      ) : results.length > 0 ? (
        <div className="space-y-3">
          <div className="text-xs font-semibold text-slate-500">Showing {results.length} results</div>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
            {results.map(p => (
              <ProductCard key={p.id} product={p} />
            ))}
          </div>
        </div>
      ) : (
        <div className="py-16 text-center space-y-3">
          <div className="text-5xl">🔍</div>
          <h3 className="font-bold text-lg text-slate-700 dark:text-slate-300">No products found</h3>
          <p className="text-xs text-slate-400">Try searching for 'milk', 'mango', 'ice cream', or 'chips'</p>
        </div>
      )}
    </div>
  );
}

// --- Product Detail View ---
function ProductDetailPage() {
  const { viewParam, navigate, addItem, cart, updateItemQty } = useApp();
  const [product, setProduct] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (viewParam) {
      API.getProductDetail(viewParam)
        .then(res => {
          setProduct(res);
          setLoading(false);
        })
        .catch(console.error);
    }
  }, [viewParam]);

  if (loading || !product) {
    return <div className="max-w-4xl mx-auto p-8"><div className="h-80 rounded-3xl skeleton-box"></div></div>;
  }

  const cartItem = cart.items.find(it => it.productId === product.id);
  const qty = cartItem ? cartItem.quantity : 0;

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      <button onClick={() => navigate("home")} className="text-xs font-bold text-indigo-600 dark:text-indigo-400 mb-6 flex items-center gap-1 hover:underline">
        ← Back to Catalog
      </button>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8 bg-white dark:bg-slate-900 p-6 md:p-8 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm">
        {/* Product Image */}
        <div className="h-72 md:h-96 rounded-2xl bg-slate-50 dark:bg-slate-800/60 p-6 flex items-center justify-center">
          <img src={product.imageUrl} alt={product.name} className="max-h-full max-w-full object-contain" />
        </div>

        {/* Product Details */}
        <div className="flex flex-col justify-between space-y-6">
          <div className="space-y-3">
            <span className="px-2.5 py-1 rounded-full bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-400 text-xs font-bold">
              ⚡ 10 Mins Delivery
            </span>
            <div className="text-xs uppercase font-bold text-slate-400 tracking-wider">{product.brand}</div>
            <h1 className="text-2xl font-extrabold text-slate-900 dark:text-white">{product.name}</h1>
            <div className="text-sm text-slate-500 font-medium">Unit: {product.unit}</div>

            <div className="flex items-baseline gap-3 pt-2">
              <span className="text-3xl font-black text-slate-900 dark:text-white">₹{product.price}</span>
              {product.originalPrice > product.price && (
                <span className="text-base text-slate-400 line-through">₹{product.originalPrice}</span>
              )}
              {product.discountPercent > 0 && (
                <span className="px-2 py-0.5 rounded-full bg-emerald-600 text-white font-extrabold text-xs">
                  {product.discountPercent}% OFF
                </span>
              )}
            </div>

            <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed pt-2">
              {product.description}
            </p>
          </div>

          <div className="pt-6 border-t border-slate-100 dark:border-slate-800 flex items-center gap-4">
            {qty > 0 ? (
              <div className="flex items-center bg-indigo-600 rounded-2xl text-white font-bold text-base px-3 py-2 shadow-lg">
                <button onClick={() => updateItemQty(product.id, qty - 1)} className="px-4 py-1 text-xl hover:bg-indigo-700 rounded-xl">
                  −
                </button>
                <span className="px-4">{qty} in Cart</span>
                <button onClick={() => updateItemQty(product.id, qty + 1)} className="px-4 py-1 text-xl hover:bg-indigo-700 rounded-xl">
                  +
                </button>
              </div>
            ) : (
              <button
                onClick={() => addItem(product.id, 1)}
                className="flex-1 py-3.5 rounded-2xl bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-sm shadow-xl shadow-indigo-500/20 active:scale-95 transition"
              >
                Add to Cart • ₹{product.price}
              </button>
            )}
            <button
              onClick={() => navigate("cart")}
              className="px-5 py-3.5 rounded-2xl bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-200 font-bold text-sm"
            >
              View Cart ➔
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// --- Cart & Best Offer Summary Page ---
function CartPage() {
  const { cart, updateItemQty, navigate, activeAccount, activeCoupon, setActiveCoupon, showToast, refreshCart } = useApp();
  const [couponInput, setCouponInput] = useState("");
  const [evalData, setEvalData] = useState(null);

  useEffect(() => {
    API.getOffers().then(res => setEvalData(res.evaluation)).catch(console.error);
  }, [cart.cartTotal]);

  const handleApplyCoupon = async () => {
    if (!couponInput.trim()) return;
    try {
      const res = await API.validateCoupon(couponInput.trim());
      setActiveCoupon({ code: res.code, discountAmount: res.discount, title: res.title });
      showToast(`Coupon ${res.code} applied! Saved ₹${res.discount}`);
      setCouponInput("");
    } catch (err) {
      showToast(err.message, "error");
    }
  };

  const handleAutoApply = async () => {
    try {
      const res = await API.autoApplyBestOffer();
      if (res.success) {
        setActiveCoupon(res.appliedOffer);
        showToast(`Auto-applied best coupon: ${res.appliedOffer.code}! Saved ₹${res.appliedOffer.discountAmount}`);
        await refreshCart();
      }
    } catch (err) {
      showToast(err.message, "error");
    }
  };

  if (cart.itemCount === 0) {
    return (
      <div className="max-w-md mx-auto py-16 px-4 text-center space-y-4">
        <div className="text-6xl">🛒</div>
        <h2 className="text-xl font-extrabold text-slate-900 dark:text-white">Your Cart is Empty</h2>
        <p className="text-xs text-slate-500">
          Account: <span className="font-semibold">{activeAccount?.displayName}</span>
        </p>
        <button
          onClick={() => navigate("home")}
          className="px-6 py-3 rounded-2xl bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs shadow-lg transition"
        >
          Browse Fresh Groceries
        </button>
      </div>
    );
  }

  const couponDiscount = activeCoupon ? activeCoupon.discountAmount : 0;
  const deliveryFee = cart.deliveryFee;
  const handlingFee = 4.0;
  const finalPayable = Math.max(0, (cart.cartTotal - couponDiscount) + deliveryFee + handlingFee);

  return (
    <div className="max-w-4xl mx-auto px-4 py-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-black text-slate-900 dark:text-white">Review Order</h1>
          <p className="text-xs text-slate-500">Account: <b>{activeAccount?.displayName}</b> ({activeAccount?.maskedMobile})</p>
        </div>
        <span className="text-xs font-bold text-emerald-600 bg-emerald-50 dark:bg-emerald-950/60 px-3 py-1 rounded-full">
          ⚡ 10 Mins Delivery
        </span>
      </div>

      {/* Free Delivery Meter */}
      <div className="p-4 rounded-2xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800/60 flex items-center justify-between text-xs font-semibold text-emerald-800 dark:text-emerald-300">
        <div className="flex items-center gap-2">
          <span>🚚</span>
          {cart.deliveryFee === 0 ? (
            <span>You unlocked <b>FREE Express Delivery</b>!</span>
          ) : (
            <span>Add ₹{cart.amountNeededForFreeDelivery} more for <b>FREE Delivery</b></span>
          )}
        </div>
        <span className="font-bold">Threshold: ₹{cart.freeDeliveryThreshold}</span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Cart Items List */}
        <div className="md:col-span-2 space-y-3">
          {cart.items.map(it => (
            <div
              key={it.id}
              className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 flex items-center justify-between gap-4 shadow-sm"
            >
              <div className="flex items-center gap-3">
                <div className="w-14 h-14 rounded-xl bg-slate-50 dark:bg-slate-800 p-1 flex items-center justify-center">
                  <img src={it.imageUrl} alt={it.name} className="max-h-full max-w-full object-contain" />
                </div>
                <div>
                  <h4 className="font-bold text-sm text-slate-900 dark:text-white">{it.name}</h4>
                  <div className="text-xs text-slate-400 font-medium">{it.unit}</div>
                  <div className="text-xs font-bold text-slate-900 dark:text-slate-100 mt-1">₹{it.price} each</div>
                </div>
              </div>

              <div className="flex items-center gap-3">
                <div className="flex items-center bg-indigo-50 dark:bg-indigo-950/80 rounded-xl border border-indigo-200 dark:border-indigo-800/60 text-indigo-700 dark:text-indigo-300 font-bold text-xs">
                  <button onClick={() => updateItemQty(it.productId, it.quantity - 1)} className="px-2.5 py-1 hover:bg-indigo-200 dark:hover:bg-indigo-900 rounded-l-xl">
                    −
                  </button>
                  <span className="px-2">{it.quantity}</span>
                  <button onClick={() => updateItemQty(it.productId, it.quantity + 1)} className="px-2.5 py-1 hover:bg-indigo-200 dark:hover:bg-indigo-900 rounded-r-xl">
                    +
                  </button>
                </div>
                <div className="font-extrabold text-sm text-slate-900 dark:text-white min-w-[50px] text-right">
                  ₹{it.total}
                </div>
              </div>
            </div>
          ))}

          {/* Auto Apply Best Offer CTA */}
          <div className="p-4 rounded-2xl bg-gradient-to-r from-indigo-900 to-violet-900 text-white flex items-center justify-between gap-3 shadow-md">
            <div>
              <div className="text-xs font-bold text-emerald-400 uppercase tracking-wider">Engine Recommendation</div>
              <div className="text-sm font-extrabold">
                {evalData?.hasEligibleOffer ? `Save ₹${evalData.recommendedOffer.discountAmount} with ${evalData.recommendedOffer.code}` : "Compare all coupons"}
              </div>
            </div>
            <button
              onClick={handleAutoApply}
              className="px-4 py-2 rounded-xl bg-emerald-500 hover:bg-emerald-600 text-slate-950 font-black text-xs shadow-md active:scale-95 transition"
            >
              AUTO APPLY
            </button>
          </div>
        </div>

        {/* Bill Summary Breakdown */}
        <div className="space-y-4">
          <div className="p-5 rounded-3xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-4 shadow-sm">
            <h3 className="font-extrabold text-sm text-slate-900 dark:text-white uppercase tracking-wider">Bill Summary</h3>
            
            <div className="space-y-2 text-xs">
              <div className="flex justify-between text-slate-500">
                <span>Item Total (MRP)</span>
                <span>₹{cart.mrpTotal}</span>
              </div>
              <div className="flex justify-between text-emerald-600 font-semibold">
                <span>Product Discounts</span>
                <span>-₹{cart.itemDiscount}</span>
              </div>
              <div className="flex justify-between text-slate-500">
                <span>Subtotal</span>
                <span>₹{cart.cartTotal}</span>
              </div>
              {activeCoupon && (
                <div className="flex justify-between text-indigo-600 font-bold">
                  <span>Coupon ({activeCoupon.code})</span>
                  <span>-₹{activeCoupon.discountAmount}</span>
                </div>
              )}
              <div className="flex justify-between text-slate-500">
                <span>Delivery Fee</span>
                <span>{cart.deliveryFee === 0 ? "FREE" : `₹${cart.deliveryFee}`}</span>
              </div>
              <div className="flex justify-between text-slate-500">
                <span>Platform & Handling</span>
                <span>₹{handlingFee}</span>
              </div>

              <div className="pt-3 border-t border-slate-100 dark:border-slate-800 flex justify-between font-black text-base text-slate-900 dark:text-white">
                <span>To Pay</span>
                <span>₹{finalPayable}</span>
              </div>
            </div>

            {/* Promo Code Input */}
            <div className="pt-2 flex gap-2">
              <input
                type="text"
                placeholder="Promo Code"
                value={couponInput}
                onChange={(e) => setCouponInput(e.target.value.toUpperCase())}
                className="w-full px-3 py-2 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs font-mono font-bold uppercase focus:outline-none"
              />
              <button
                onClick={handleApplyCoupon}
                className="px-3 py-2 rounded-xl bg-indigo-600 text-white font-bold text-xs"
              >
                Apply
              </button>
            </div>

            <button
              onClick={() => navigate("checkout")}
              className="w-full py-3.5 rounded-2xl bg-gradient-to-r from-emerald-600 to-emerald-500 hover:from-emerald-700 text-white font-extrabold text-sm shadow-xl shadow-emerald-500/20 active:scale-95 transition"
            >
              Proceed to Checkout • ₹{finalPayable}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// --- Checkout Page ---
function CheckoutPage() {
  const { cart, activeAccount, activeCoupon, navigate, showToast, refreshCart } = useApp();
  const [paymentMethod, setPaymentMethod] = useState("UPI");
  const [placing, setPlacing] = useState(false);

  const couponCode = activeCoupon ? activeCoupon.code : null;
  const couponDiscount = activeCoupon ? activeCoupon.discountAmount : 0;
  const deliveryFee = cart.deliveryFee;
  const handlingFee = 4.0;
  const finalPayable = Math.max(0, (cart.cartTotal - couponDiscount) + deliveryFee + handlingFee);

  const handlePlaceOrder = async () => {
    setPlacing(true);
    try {
      const res = await API.placeOrder(paymentMethod, null, couponCode);
      if (res.success) {
        showToast("🎉 Order placed successfully with 10-min delivery!");
        await refreshCart();
        navigate("orders");
      }
    } catch (err) {
      showToast(err.message, "error");
    } finally {
      setPlacing(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto px-4 py-8 space-y-6">
      <h1 className="text-2xl font-black text-slate-900 dark:text-white">Secure Checkout</h1>

      {/* Address Card */}
      <div className="p-5 rounded-3xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-xs font-bold uppercase tracking-wider text-slate-400">Delivering To</span>
          <span className="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 text-[10px] font-bold">10 Mins ETA</span>
        </div>
        <h4 className="font-bold text-slate-900 dark:text-white text-base">Home (Default)</h4>
        <p className="text-xs text-slate-500">Flat 402, Building B, Emerald Heights, BKC, Mumbai - 400051</p>
      </div>

      {/* Payment Selection */}
      <div className="p-5 rounded-3xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-3">
        <span className="text-xs font-bold uppercase tracking-wider text-slate-400">Payment Options (Zero raw card storage)</span>
        <div className="space-y-2.5">
          {[
            { id: "UPI", title: "UPI (Google Pay, PhonePe, Paytm)", icon: "📱", desc: "Instant 1-click payment" },
            { id: "CARD", title: "Credit / Debit Card", icon: "💳", desc: "Visa, Mastercard, RuPay (3DS Handoff)" },
            { id: "COD", title: "Cash on Delivery", icon: "💵", desc: "Pay cash or UPI at delivery" },
          ].map((m) => (
            <div
              key={m.id}
              onClick={() => setPaymentMethod(m.id)}
              className={`p-3.5 rounded-2xl border cursor-pointer flex items-center justify-between transition ${
                paymentMethod === m.id
                  ? "border-indigo-600 bg-indigo-50/60 dark:bg-indigo-950/40 ring-2 ring-indigo-500/20"
                  : "border-slate-200 dark:border-slate-800"
              }`}
            >
              <div className="flex items-center gap-3">
                <span className="text-xl">{m.icon}</span>
                <div>
                  <div className="font-bold text-sm text-slate-900 dark:text-white">{m.title}</div>
                  <div className="text-xs text-slate-500">{m.desc}</div>
                </div>
              </div>
              <input type="radio" checked={paymentMethod === m.id} readOnly className="text-indigo-600" />
            </div>
          ))}
        </div>
      </div>

      {/* Final Place Order */}
      <button
        onClick={handlePlaceOrder}
        disabled={placing}
        className="w-full py-4 rounded-2xl bg-gradient-to-r from-emerald-600 to-emerald-500 hover:from-emerald-700 text-white font-black text-base shadow-xl shadow-emerald-500/20 active:scale-95 transition flex items-center justify-center gap-2"
      >
        <span>⚡</span> {placing ? "Confirming Order..." : `Pay ₹${finalPayable} & Place 10-Min Order`}
      </button>
    </div>
  );
}

// --- Orders & Tracking Page ---
function OrdersPage() {
  const { activeAccount, navigate } = useApp();
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    API.getOrders()
      .then(res => {
        setOrders(res.orders || []);
        setLoading(false);
      })
      .catch(console.error);
  }, [activeAccount?.accountId]);

  if (loading) return <div className="max-w-3xl mx-auto p-8"><div className="h-64 rounded-3xl skeleton-box"></div></div>;

  return (
    <div className="max-w-4xl mx-auto px-4 py-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-black text-slate-900 dark:text-white">Order History</h1>
          <p className="text-xs text-slate-500">Account: <b>{activeAccount?.displayName}</b></p>
        </div>
      </div>

      {orders.length === 0 ? (
        <div className="p-12 text-center rounded-3xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-3">
          <div className="text-5xl">📦</div>
          <h3 className="font-bold text-slate-700 dark:text-slate-300">No orders yet</h3>
          <p className="text-xs text-slate-500">Orders placed on this shopping account will appear here.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {orders.map(o => (
            <div
              key={o.id}
              className="p-5 rounded-3xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-4"
            >
              <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3">
                <div>
                  <span className="font-mono font-bold text-xs text-indigo-600 dark:text-indigo-400">{o.orderCode}</span>
                  <div className="text-xs text-slate-400 mt-0.5">{new Date(o.placedAt).toLocaleString()}</div>
                </div>
                <span className="px-3 py-1 rounded-full bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-400 text-xs font-black">
                  {o.status}
                </span>
              </div>

              {/* Items summary */}
              <div className="space-y-1.5 text-xs">
                {o.items.map((it, idx) => (
                  <div key={idx} className="flex justify-between text-slate-700 dark:text-slate-300">
                    <span>{it.name} x {it.quantity}</span>
                    <span className="font-bold">₹{it.total}</span>
                  </div>
                ))}
              </div>

              {/* Status Stepper */}
              <div className="pt-2 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between text-xs">
                <div className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-ping"></span>
                  <span className="font-bold text-emerald-600 dark:text-emerald-400">Rider Arriving in ~{o.etaMinutes} mins</span>
                </div>
                <div className="font-black text-sm text-slate-900 dark:text-white">
                  Total: ₹{o.totalAmount}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// --- Backup (JSON Import / Export) Page ---
function BackupPage() {
  const { showToast, refreshAccounts } = useApp();
  const [jsonText, setJsonText] = useState("");
  const [preview, setPreview] = useState(null);

  const handleExport = async () => {
    try {
      const data = await API.exportAccounts();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `zepto_accounts_backup_${Date.now()}.json`;
      a.click();
      showToast("JSON backup downloaded successfully!");
    } catch (err) {
      showToast(err.message, "error");
    }
  };

  const handlePreview = async () => {
    try {
      const parsed = JSON.parse(jsonText);
      const res = await API.previewImport(parsed);
      setPreview(res);
      showToast("Schema validated! Preview ready.");
    } catch (err) {
      showToast("Invalid JSON syntax: " + err.message, "error");
    }
  };

  const handleConfirmImport = async () => {
    try {
      const parsed = JSON.parse(jsonText);
      const res = await API.confirmImport(parsed);
      showToast(res.message);
      setPreview(null);
      setJsonText("");
      await refreshAccounts();
    } catch (err) {
      showToast(err.message, "error");
    }
  };

  return (
    <div className="max-w-4xl mx-auto px-4 py-8 space-y-8">
      <div>
        <h1 className="text-2xl font-black text-slate-900 dark:text-white">Account Backup & Portability</h1>
        <p className="text-xs text-slate-500">Securely export or restore multiple shopping account profiles</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Export Card */}
        <div className="p-6 rounded-3xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-4 shadow-sm flex flex-col justify-between">
          <div className="space-y-2">
            <div className="w-10 h-10 rounded-2xl bg-indigo-100 text-indigo-600 flex items-center justify-center font-bold">
              💾
            </div>
            <h3 className="font-extrabold text-base text-slate-900 dark:text-white">EXPORT ACCOUNTS</h3>
            <p className="text-xs text-slate-500 leading-relaxed">
              Download your multi-account profiles, addresses, preferences, and metadata in JSON format. Sensitive session tokens and OTPs are safely omitted.
            </p>
          </div>
          <button
            onClick={handleExport}
            className="w-full py-3 rounded-2xl bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs shadow-md transition"
          >
            Download JSON Backup
          </button>
        </div>

        {/* Import Card */}
        <div className="p-6 rounded-3xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-4 shadow-sm">
          <div className="space-y-2">
            <div className="w-10 h-10 rounded-2xl bg-emerald-100 text-emerald-600 flex items-center justify-center font-bold">
              📥
            </div>
            <h3 className="font-extrabold text-base text-slate-900 dark:text-white">IMPORT ACCOUNTS</h3>
            <p className="text-xs text-slate-500 leading-relaxed">
              Paste or upload your JSON backup to restore accounts. Duplicates are safely detected.
            </p>
          </div>

          <textarea
            rows="4"
            value={jsonText}
            onChange={(e) => setJsonText(e.target.value)}
            placeholder='Paste {"version": 1, "accounts": [...]} here'
            className="w-full p-3 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs font-mono focus:outline-none"
          ></textarea>

          <div className="flex gap-2">
            <button
              onClick={handlePreview}
              className="flex-1 py-2.5 rounded-xl bg-slate-200 dark:bg-slate-700 text-slate-800 dark:text-slate-200 font-bold text-xs"
            >
              Preview Validation
            </button>
            {preview && (
              <button
                onClick={handleConfirmImport}
                className="flex-1 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs"
              >
                Confirm Restore ({preview.newCount} New)
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// --- Offers Page ---
function OffersPage() {
  const { cart, setActiveCoupon, showToast, navigate } = useApp();
  const [offers, setOffers] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    API.getOffers()
      .then(res => {
        setOffers(res.availableOffers || []);
        setLoading(false);
      })
      .catch(console.error);
  }, [cart.cartTotal]);

  const applyCode = (code) => {
    API.validateCoupon(code)
      .then(res => {
        setActiveCoupon({ code: res.code, discountAmount: res.discount, title: res.title });
        showToast(`Applied ${res.code}! Saved ₹${res.discount}`);
        navigate("cart");
      })
      .catch(err => showToast(err.message, "error"));
  };

  return (
    <div className="max-w-4xl mx-auto px-4 py-8 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-black text-slate-900 dark:text-white">Active Promotional Coupons</h1>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {offers.map(off => (
          <div
            key={off.id}
            className="p-5 rounded-3xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col justify-between space-y-4"
          >
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="font-mono font-black text-sm px-3 py-1 rounded-xl bg-indigo-50 dark:bg-indigo-950 text-indigo-600 dark:text-indigo-400 border border-indigo-200 dark:border-indigo-800">
                  {off.code}
                </span>
                <span className={`text-[11px] font-bold px-2 py-0.5 rounded-full ${
                  off.isEligible ? "bg-emerald-100 text-emerald-800" : "bg-slate-100 text-slate-500"
                }`}>
                  {off.isEligible ? "Eligible" : `Add ₹${off.amountNeeded} more`}
                </span>
              </div>
              <h3 className="font-extrabold text-sm text-slate-900 dark:text-white">{off.title}</h3>
              <p className="text-xs text-slate-500 mt-1">{off.description}</p>
            </div>

            <button
              onClick={() => applyCode(off.code)}
              className="w-full py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs transition"
            >
              Apply Coupon ➔
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

// --- Main App Shell ---
function App() {
  const { currentView, toasts } = useApp();

  return (
    <div className="min-h-screen flex flex-col">
      <Header />

      <main className="flex-1 pb-16 md:pb-6">
        {currentView === "home" && <HomePage />}
        {currentView === "categories" && <SearchPage />}
        {currentView === "search" && <SearchPage />}
        {currentView === "product" && <ProductDetailPage />}
        {currentView === "cart" && <CartPage />}
        {currentView === "offers" && <OffersPage />}
        {currentView === "checkout" && <CheckoutPage />}
        {currentView === "orders" && <OrdersPage />}
        {currentView === "backup" && <BackupPage />}
      </main>

      <BottomNav />
      <AccountModal />

      {/* Toast Notification Container */}
      <div className="fixed bottom-20 md:bottom-6 right-4 z-50 space-y-2">
        {toasts.map(t => (
          <div
            key={t.id}
            className={`px-4 py-3 rounded-2xl shadow-xl text-xs font-bold flex items-center gap-2 transform transition-all animate-bounce ${
              t.type === "error" ? "bg-red-600 text-white" : "bg-slate-900 text-white border border-slate-700"
            }`}
          >
            <span>{t.type === "error" ? "⚠️" : "✨"}</span>
            <span>{t.message}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// Mount React Root
const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <AppProvider>
    <App />
  </AppProvider>
);
