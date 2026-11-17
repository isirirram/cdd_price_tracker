import { useState } from "react";

function AddProduct({ onAddProduct, onCancel }) {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();

    const formData = new FormData(e.target);
    const product = {
      product_url: formData.get("product_url").trim(),
      target_price: Number(formData.get("target_price")),
    };

    const email = formData.get("alert_email").trim();
    if (email) product.alert_email = email;

    try {
      setSaving(true);
      setError("");
      await onAddProduct(product);
    } catch (err) {
      setError(err.message || "Unable to add product.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="add-product-page">
      <div className="add-product-card">
        <h2>Add New Product</h2>
        <p>Enter the product details to start tracking its price.</p>

        <form onSubmit={handleSubmit}>
          <label>Product URL</label>
          <input
            type="url"
            name="product_url"
            placeholder="e.g. http://127.0.0.1:8001/products/product-001"
            required
          />

          <label>Target Price (₹)</label>
          <input
            type="number"
            name="target_price"
            placeholder="Enter your target price"
            min="1"
            step="any"
            required
          />

          <label>Email for price-drop alert (optional)</label>
          <input
            type="email"
            name="alert_email"
            placeholder="you@example.com"
          />

          {error && <p style={{ color: "#E35336" }}>{error}</p>}

          <div className="add-product-actions">
            <button type="button" onClick={onCancel} disabled={saving}>
              Cancel
            </button>

            <button type="submit" disabled={saving}>
              {saving ? "Adding…" : "Start Tracking"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default AddProduct;
