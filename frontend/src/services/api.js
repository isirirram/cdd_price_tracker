
const API_BASE_URL =
  import.meta.env.VITE_API_URL || "http://localhost:8000";

// Common API request handler
const apiRequest = async (endpoint, options = {}) => {
  try {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...options.headers,
      },
    });

    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      throw new Error(
        data.detail || data.message || "Something went wrong"
      );
    }

    return data;
  } catch (error) {
    console.error("API Error:", error.message);
    throw error;
  }
};

// ---------------- PRODUCTS ----------------

// Get all tracked products
export const getProducts = () => {
  return apiRequest("/products");
};

// Add a product
export const addProduct = (productData) => {
  return apiRequest("/products", {
    method: "POST",
    body: JSON.stringify(productData),
  });
};

// Get product details
export const getProductById = (productId) => {
  return apiRequest(`/products/${productId}`);
};

// Delete a product
export const deleteProduct = (productId) => {
  return apiRequest(`/products/${productId}`, {
    method: "DELETE",
  });
};

// ---------------- PRICE TRACKING ----------------

// Get product price history
export const getPriceHistory = (productId) => {
  return apiRequest(`/products/${productId}/history`);
};

// Request an immediate price check
export const checkProductNow = (productId) => {
  return apiRequest(`/products/${productId}/check`, {
    method: "POST",
  });
};

// ---------------- NOTIFICATIONS ----------------

// Update or clear notification email
export const updateNotifyEmail = (productId, notifyEmail) => {
  return apiRequest(`/products/${productId}/notify-email`, {
    method: "PATCH",
    body: JSON.stringify({
      notify_email: notifyEmail || null,
    }),
  });
};

// ---------------- INSIGHTS ----------------

// Get best time to buy insights
export const getProductInsights = (productId) => {
  return apiRequest(`/products/${productId}/insights`);
};

// Get price drop report
export const getProductDrops = (productId) => {
  return apiRequest(`/products/${productId}/drops`);
};

// ---------------- SALE EVENTS ----------------

// Get all sale events
export const getSaleEvents = () => {
  return apiRequest("/sale-events");
};

// Add a sale event
export const addSaleEvent = (eventData) => {
  return apiRequest("/sale-events", {
    method: "POST",
    body: JSON.stringify(eventData),
  });
};

// Delete a sale event
export const deleteSaleEvent = (eventId) => {
  return apiRequest(`/sale-events/${eventId}`, {
    method: "DELETE",
  });
};

// ---------------- BUDGET ----------------

// Get budget plan
export const getBudgetPlan = () => {
  return apiRequest("/budget");
};

// Set monthly budget
export const setBudget = (monthlyBudget, spent) => {
  return apiRequest("/budget", {
    method: "PUT",
    body: JSON.stringify({
      monthly_budget: monthlyBudget,
      spent_this_month: spent,
      user_id: "demo-user",
    }),
  });
};

// ---------------- CHATBOT ----------------

// Get chatbot status (AI or Offline)
export const getChatStatus = () => {
  return apiRequest("/chat/status");
};

// Send message to chatbot
export const sendChatMessage = (message, history = []) => {
  return apiRequest("/chat", {
    method: "POST",
    body: JSON.stringify({
      message,
      history,
      user_id: "demo-user",
    }),
  });
};
