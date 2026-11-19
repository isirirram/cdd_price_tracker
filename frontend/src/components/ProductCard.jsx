import { productStatus } from "../utils/productStatus";
import ProductImage from "./ProductImage";

const formatPrice = (price) => `₹${Number(price).toLocaleString("en-IN")}`;

function ProductCard({ product, onViewHistory, onDelete, onCheckNow, checking }) {
  const status = productStatus(product);

  return (
    <div className="product-card">
      <ProductImage product={product} size={55} />

      <div className="product-info">
        <p className="product-category">{product.site?.toUpperCase()}</p>

        <h3>{product.product_name}</h3>

        <p>
          Current Price:{" "}
          <strong>
            {product.current_price != null
              ? formatPrice(product.current_price)
              : "Not checked yet"}
          </strong>
        </p>

        <p>
          Target Price: <strong>{formatPrice(product.target_price)}</strong>
        </p>

        <p style={{ color: status.color, fontWeight: 600 }}>{status.text}</p>

        <p style={{ fontSize: "0.85em", color: "#777" }}>
          Alerts to: {product.notify_email || "default email"}
          {product.telegram_chat_id ? ` · Telegram ${product.telegram_chat_id}` : ""}
        </p>

        {product.last_checked_at && (
          <p style={{ fontSize: "0.85em", color: "#777" }}>
            Last checked: {new Date(product.last_checked_at).toLocaleString("en-IN")}
          </p>
        )}

        <div className="product-card-actions">
          {onViewHistory && (
            <button onClick={onViewHistory}>View Price History</button>
          )}

          {onCheckNow && (
            <button onClick={onCheckNow} disabled={checking}>
              {checking ? "Checking…" : "Check Now"}
            </button>
          )}

          {onDelete && <button onClick={onDelete}>Remove</button>}
        </div>
      </div>
    </div>
  );
}

export default ProductCard;
