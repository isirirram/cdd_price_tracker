
const API_BASE_URL =
  import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

const USER_ID = "demo-user";

// Common API request function
async function apiRequest(endpoint, options = {}) {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    // Validation errors come back as {detail: "Invalid input", errors: [...]}
    const firstError = data.errors?.[0];
    const message = firstError
      ? `${firstError.loc?.slice(-1)[0]}: ${firstError.msg}`
      : data.detail;
    throw new Error(message || "Something went wrong");
  }

  return data;
}

// PRODUCT APIs

export function getProducts() {
  return apiRequest("/products");
}

export function addProduct(product) {
  return apiRequest("/products", {
    method: "POST",
    body: JSON.stringify({
      ...product,
      user_id: USER_ID,
    }),
  });
}

export function deleteProduct(id) {
  return apiRequest(`/products/${id}`, {
    method: "DELETE",
  });
}

export function getProductById(id) {
  return apiRequest(`/products/${id}`);
}

// Change (or clear with null) the email that gets the price-drop alert
export function updateNotifyEmail(id, email) {
  return apiRequest(`/products/${id}/notify-email`, {
    method: "PATCH",
    body: JSON.stringify({ notify_email: email || null }),
  });
}

// Ask the worker to re-check this product's price right now
export function checkProductNow(id) {
  return apiRequest(`/products/${id}/check`, {
    method: "POST",
  });
}

export function getPriceHistory(id) {
  return apiRequest(`/products/${id}/history`);
}

// FEATURE 1: BEST TIME TO BUY

export function getProductInsights(id) {
  return apiRequest(`/products/${id}/insights`);
}

// FEATURE 2: FESTIVAL / SALE EVENT TRACKER

export function getProductDrops(id) {
  return apiRequest(`/products/${id}/drops`);
}

export function getSaleEvents() {
  return apiRequest("/sale-events");
}

export function addSaleEvent(event) {
  return apiRequest("/sale-events", {
    method: "POST",
    body: JSON.stringify(event),
  });
}

export function deleteSaleEvent(id) {
  return apiRequest(`/sale-events/${id}`, {
    method: "DELETE",
  });
}

// FEATURE 3: MONTHLY BUDGET TRACKER

export function setBudget(monthlyBudget, spentThisMonth = 0) {
  return apiRequest("/budget", {
    method: "PUT",
    body: JSON.stringify({
      monthly_budget: monthlyBudget,
      spent_this_month: spentThisMonth,
      user_id: USER_ID,
    }),
  });
}

export function getBudgetPlan() {
  return apiRequest(`/budget?user_id=${USER_ID}`);
}

// AI PRICE ASSISTANT

export function sendChatMessage(message, history = []) {
  return apiRequest("/chat", {
    method: "POST",
    body: JSON.stringify({ message, history, user_id: USER_ID }),
  });
}

export function getChatStatus() {
  return apiRequest("/chat/status");
}

// PRICE COMPARISON (same product on other Shopify / WooCommerce stores)

export function getComparison(id) {
  return apiRequest(`/products/${id}/compare`);
}

export function addCompareStore(id, productUrl) {
  return apiRequest(`/products/${id}/compare`, {
    method: "POST",
    body: JSON.stringify({ product_url: productUrl }),
  });
}
