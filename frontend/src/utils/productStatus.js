// Works out what to show under a product, using the fields the worker fills in
export function productStatus(product) {
  if (product.last_error && product.current_price == null) {
    return { text: `Couldn't fetch price: ${product.last_error}`, color: "#E35336" };
  }
  if (product.current_price == null) {
    return { text: "Waiting for first price check…", color: "#777777" };
  }
  if (product.current_price <= product.target_price) {
    return {
      text: product.alert_sent ? "Target reached · alert sent ✓" : "Target reached!",
      color: "#2E7D32",
    };
  }
  return { text: "Tracking", color: "#A0522D" };
}
