import { useCallback, useEffect, useState } from "react";
import { addCompareStore, getComparison } from "../services/api";

const formatPrice = (price) =>
  price == null ? "—" : `₹${Number(price).toLocaleString("en-IN")}`;

const PLATFORM_LABEL = {
  shopify: "Shopify",
  woocommerce: "WooCommerce",
  local_store: "Demo Store",
};

// "Same product on other stores": prices of one product across Shopify and
// WooCommerce stores, cheapest first, plus a form to add another store link.
function CompareStores({ product }) {
  const [data, setData] = useState(null);
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");
  const [adding, setAdding] = useState(false);

  const load = useCallback(
    () =>
      getComparison(product.id)
        .then((result) => {
          setData(result);
          setError("");
        })
        .catch((err) => setError(err.message || "Unable to load comparison.")),
    [product.id]
  );

  useEffect(() => {
    load();
  }, [load]);

  const handleAdd = async (e) => {
    e.preventDefault();
    try {
      setAdding(true);
      setError("");
      await addCompareStore(product.id, url.trim());
      setUrl("");
      await load();
      window.dispatchEvent(new Event("products-changed"));
      // the worker fetches the new store's price in the background
      setTimeout(load, 4000);
    } catch (err) {
      setError(err.message || "Unable to add store.");
    } finally {
      setAdding(false);
    }
  };

  return (
    <div className="chart-card" style={{ marginTop: "25px" }}>
      <h2>Compare Prices Across Stores</h2>
      <p>
        Track the same product on other Shopify or WooCommerce stores and see
        where it's cheapest.
      </p>

      {data && data.offers.length > 0 && (
        <table className="compare-table">
          <thead>
            <tr>
              <th>Store</th>
              <th>Platform</th>
              <th>Price</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {data.offers.map((offer) => (
              <tr key={offer.id} className={offer.is_cheapest ? "cheapest" : ""}>
                <td>
                  <a href={offer.product_url} target="_blank" rel="noopener noreferrer">
                    {offer.site}
                  </a>
                </td>
                <td>{PLATFORM_LABEL[offer.platform] || offer.platform || "—"}</td>
                <td>
                  {offer.current_price != null
                    ? formatPrice(offer.current_price)
                    : offer.last_error
                    ? `Couldn't fetch: ${offer.last_error}`
                    : "Checking…"}
                </td>
                <td>{offer.is_cheapest && data.store_count > 1 ? "✓ Cheapest" : ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {data && data.max_saving > 0 && (
        <p style={{ color: "#2E7D32", fontWeight: 600 }}>
          Buy at {data.cheapest_site} and save up to {formatPrice(data.max_saving)}.
        </p>
      )}

      <form className="compare-form" onSubmit={handleAdd}>
        <input
          type="url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://another-store.com/products/same-item"
          required
        />
        <button type="submit" disabled={adding}>
          {adding ? "Adding…" : "+ Add Store"}
        </button>
      </form>

      {error && <p style={{ color: "#E35336" }}>{error}</p>}
    </div>
  );
}

export default CompareStores;
