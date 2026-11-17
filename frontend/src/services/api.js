
const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

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
      throw new Error(data.detail || data.message || "Something went wrong");
    }

    return data;
  } catch (error) {
    console.error("API Error:", error.message);
    throw error;
  }
};

// Get all products
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

// Get product price history
export const getPriceHistory = (productId) => {
  return apiRequest(`/products/${productId}/history`);
};

// Update product target price
export const updateTargetPrice = (productId, targetPrice) => {
  return apiRequest(`/products/${productId}`, {
    method: "PATCH",
    body: JSON.stringify({ target_price: targetPrice }),
  });
};

// Get product insights (best time to buy)
export const getProductInsights = (productId) => {
  return apiRequest(`/products/${productId}/insights`);
};

// Get product price drop report
export const getProductDrops = (productId) => {
  return apiRequest(`/products/${productId}/drops`);
};

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
    }),
  });
};