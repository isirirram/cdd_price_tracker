import { useState } from "react";

// Shows the scraped product photo, or the 🛍️ placeholder when there is no
// image yet or the image link is broken.
function ProductImage({ product, size = 55 }) {
  const [failedUrl, setFailedUrl] = useState(null);
  const url = product.image_url;

  if (!url || failedUrl === url) {
    return (
      <div className="product-image">
        <span style={{ fontSize: `${size}px` }}>🛍️</span>
      </div>
    );
  }

  return (
    <div className="product-image">
      <img
        src={url}
        alt={product.product_name || "Product"}
        loading="lazy"
        referrerPolicy="no-referrer"
        onError={() => setFailedUrl(url)}
      />
    </div>
  );
}

export default ProductImage;
