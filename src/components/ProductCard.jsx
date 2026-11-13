
function ProductCard({ product, onViewHistory, onDelete }) {
  return (
    <div className="product-card">
      <div className="product-image">
        <span>📦</span>
      </div>

      <h3>{product.product_name}</h3>

      <p>
        Current Price: ₹{product.current_price ?? "Loading..."}
      </p>

      <p>
        Target Price: ₹{product.target_price}
      </p>

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

