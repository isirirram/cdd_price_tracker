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

    const email = formData.get("notify_email").trim();
    if (email) product.notify_email = email;

    const telegram = formData.get("telegram_chat_id").trim();
    if (telegram) product.telegram_chat_id = telegram;

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
            name="notify_email"
            placeholder="you@example.com"
          />

          <label>Telegram chat ID for alert (optional)</label>
          <input
            type="text"
            name="telegram_chat_id"
            placeholder="e.g. 123456789 (message the bot, then use your chat id)"
            pattern="-?[0-9]{3,20}|@[A-Za-z0-9_]{5,32}"
            title="A numeric Telegram chat id, or @channelname"
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
