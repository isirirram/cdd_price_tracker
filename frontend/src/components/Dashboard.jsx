
import { useEffect, useState, useCallback } from "react";
import { getProducts, deleteProduct } from "../services/api";
import ProductCard from "./ProductCard";

function Dashboard({ onNavigate }) {
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const fetchProducts = useCallback(async () => {
    try {
      setError("");
      const data = await getProducts();
      setProducts(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(err.message || "Unable to load products.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchProducts();

    const handleProductsChanged = () => {
      fetchProducts();
    };

    window.addEventListener("products-changed", handleProductsChanged);

    return () => {
      window.removeEventListener("products-changed", handleProductsChanged);
    };
  }, [fetchProducts]);

  const handleDelete = async (id) => {
    const confirmed = window.confirm(
      "Are you sure you want to stop tracking this product?"
    );

    if (!confirmed) return;

    try {
      await deleteProduct(id);

      setProducts((previous) =>
        previous.filter((product) => product.id !== id)
      );
    } catch (err) {
      setError(err.message || "Unable to delete product.");
    }
  };

  const trackedCount = products.length;

  const priceDrops = products.filter(
    (product) =>
      product.current_price !== null &&
      product.current_price !== undefined &&
      Number(product.current_price) <= Number(product.target_price)
  ).length;

  const alertsCount = products.filter(
    (product) => product.alert_sent === true
  ).length;

  return (
    <div className="dashboard-page">
      <header className="navbar">
        <h1 className="logo">PRICE TRACKER</h1>

        <nav>
          <span onClick={() => onNavigate("dashboard")}>
            Dashboard
          </span>

          <span onClick={() => onNavigate("products")}>
            My Products
          </span>

          <span onClick={() => onNavigate("history")}>
            Price History
          </span>

          <span onClick={() => onNavigate("budget")}>
            Budget Tracker
          </span>

         
        </nav>
      </header>

      <main className="dashboard-content">
        <section className="welcome-section">
          <h2>Welcome</h2>

          <p>
            Track prices, discover deals and save money on
            your favourite products.
          </p>
        </section>

        <section className="stats-container">
          <div className="stat-card">
            <h3>Tracked Products</h3>
            <h2>{trackedCount}</h2>
          </div>

          <div className="stat-card">
            <h3>Target Price Reached</h3>
            <h2>{priceDrops}</h2>
          </div>

          <div className="stat-card">
            <h3>Alerts Sent</h3>
            <h2>{alertsCount}</h2>
          </div>
        </section>

        <section className="tracked-section">
          <div className="section-heading">
            <h2>Your Tracked Products</h2>

            <button onClick={() => onNavigate("products")}>
              + Add Product
            </button>
          </div>

          {loading && <p>Loading your products...</p>}

          {error && <p>{error}</p>}

          {!loading && !error && products.length === 0 && (
            <p>
              No products tracked yet. Add a product to start
              tracking its price!
            </p>
          )}

          {!loading && !error && products.length > 0 && (
            <div className="product-container">
              {products.map((product) => (
                <ProductCard
                  key={product.id}
                  product={product}
                  onViewHistory={() => onNavigate("history")}
                  onDelete={() => handleDelete(product.id)}
                />
              ))}
            </div>
          )}

          <p
            className="view-all"
            onClick={() => onNavigate("products")}
          >
            View All Products →
          </p>
        </section>

        <section className="activity-section">
          <h2>Recent Activity</h2>

          {products.some((product) => product.alert_sent) ? (
            <p>
              Price target reached and alert sent for a tracked product.
            </p>
          ) : (
            <p>
              Your products are being tracked. Alerts will appear
              here when a target price is reached.
            </p>
          )}
        </section>
      </main>
    </div>
  );
}

export default Dashboard;
