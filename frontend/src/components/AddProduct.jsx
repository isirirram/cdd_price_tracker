
function AddProduct({ onAddProduct, onCancel }) {
  const handleSubmit = (e) => {
    e.preventDefault();

    const formData = new FormData(e.target);

    const targetPrice = Number(formData.get("target_price"));

    // Validate target price
    if (targetPrice <= 0) {
      alert("Please enter a valid target price.");
      return;
    }

    // Prepare product details for backend
    const product = {
      product_url: formData.get("product_url").trim(),
      target_price: targetPrice,
      notify_email: formData.get("notify_email")?.trim() || null,
    };

    onAddProduct(product);
  };

  return (
    <div className="add-product-page">
      <div className="add-product-card">
        <h2>Add New Product</h2>

        <p>
          Enter a product URL and your target price to start
          tracking.
        </p>

        <form onSubmit={handleSubmit}>
          <label>Product URL</label>

          <input
            type="url"
            name="product_url"
            placeholder="Paste Amazon, Flipkart or supported product URL"
            required
          />

          <label>Target Price (₹)</label>

          <input
            type="number"
            name="target_price"
            placeholder="Enter your target price"
            min="1"
            step="0.01"
            required
          />

          <label>Email for price-drop alert (optional)</label>

          <input
            type="email"
            name="notify_email"
            placeholder="you@example.com"
          />

          <p className="scraper-info">
            Our scraper will identify the store and fetch the
            product details and current price.
          </p>

          <div className="add-product-actions">
            <button type="button" onClick={onCancel}>
              Cancel
            </button>

            <button type="submit">
              Start Tracking
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default AddProduct;
