
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
    throw new Error(data.detail || "Something went wrong");
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
