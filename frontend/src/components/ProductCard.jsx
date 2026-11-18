
function ProductCard({ product, onViewHistory, onDelete }) {
  const currentPrice = Number(product.current_price);
  const targetPrice = Number(product.target_price);

  const priceAvailable =
    product.current_price !== null &&
    product.current_price !== undefined;

  const targetReached =
    priceAvailable && currentPrice <= targetPrice;

  return (
    <div className="product-card">
      <div className="product-image">
        {product.image_url ? (
          <img
            src={product.image_url}
            alt={product.product_name || "Product"}
            onError={(e) => {
              e.target.style.display = "none";
            }}
          />
        ) : (
          <span>📦</span>
        )}
      </div>

      <h3>{product.product_name || "Product name unavailable"}</h3>

      <p>
        Current Price: ₹
        {priceAvailable
          ? currentPrice.toLocaleString("en-IN")
          : "Waiting for first price check"}
      </p>

      <p>
        Target Price: ₹
        {targetPrice.toLocaleString("en-IN")}
      </p>

      <p>
        Store: {product.site || "Unknown"}
      </p>

      <p>
        Status:{" "}
        {!priceAvailable
          ? "Waiting for price update"
          : targetReached
          ? "Target price reached"
          : "Tracking"}
      </p>

      <p>
        Notification:{" "}
        {product.alert_sent ? "Alert sent" : "No alert sent"}
      </p>

      {product.last_checked_at && (
        <p>
          Last Checked:{" "}
          {new Date(product.last_checked_at).toLocaleString("en-IN")}
        </p>
      )}

      {product.last_error && (
        <p className="product-error">
          {product.last_error}
        </p>
      )}

      <div className="product-card-actions">
        <button onClick={onViewHistory}>
          View History
        </button>

        <button onClick={onDelete}>
          Delete
        </button>
      </div>
    </div>
  );
}

export default ProductCard;
