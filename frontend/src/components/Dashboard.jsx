import { useEffect, useState } from "react";
import { getProducts } from "../services/api";
import Header from "./Header";
import ProductCard from "./ProductCard";

function Dashboard({ onNavigate }) {
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const load = () =>
      getProducts()
        .then(setProducts)
        .catch((err) => setError(err.message || "Unable to load products."))
        .finally(() => setLoading(false));

    load();
    // the chat assistant fires this after adding a product
    window.addEventListener("products-changed", load);
    return () => window.removeEventListener("products-changed", load);
  }, []);

  // Real numbers from the API instead of hardcoded ones
  const priced = products.filter((p) => p.current_price != null);
  const atTarget = priced.filter((p) => p.current_price <= p.target_price);
  const alertsSent = products.filter((p) => p.alert_sent);

  // Most recently checked products first
  const recent = [...priced]
    .filter((p) => p.last_checked_at)
    .sort((a, b) => new Date(b.last_checked_at) - new Date(a.last_checked_at))
    .slice(0, 5);

  return (
    <div className="dashboard-page">
      <Header onNavigate={onNavigate} active="dashboard" />

      <main className="dashboard-content">
        <section className="welcome-section">
          <h2>Welcome</h2>
          <p>Track prices, discover deals and save money on your favourite products</p>
        </section>

        {error && <p style={{ color: "#E35336" }}>{error}</p>}

        <section className="stats-container">
          <div className="stat-card">
            <h3>Tracked Products</h3>
            <h2>{loading ? "…" : products.length}</h2>
          </div>
          <div className="stat-card">
            <h3>At / Below Target</h3>
            <h2>{loading ? "…" : atTarget.length}</h2>
          </div>
          <div className="stat-card">
            <h3>Alerts Sent</h3>
            <h2>{loading ? "…" : alertsSent.length}</h2>
          </div>
        </section>

        <section className="tracked-section">
          <div className="section-heading">
            <h2>Your Tracked Products</h2>
            <button onClick={() => onNavigate("products")}>+ Add Product</button>
          </div>

          {!loading && products.length === 0 ? (
            <p>You aren't tracking anything yet. Add your first product!</p>
          ) : (
            <div className="product-container">
              {products.slice(0, 3).map((product) => (
                <ProductCard
                  key={product.id}
                  product={product}
                  onViewHistory={() => onNavigate("history", product.id)}
                />
              ))}
            </div>
          )}

          <p className="view-all" onClick={() => onNavigate("products")}>
            View All Products →
          </p>
        </section>

        <section className="activity-section">
          <h2>Recent Activity</h2>
          {recent.length === 0 ? (
            <p>No price checks yet.</p>
          ) : (
            recent.map((p) => (
              <p key={p.id}>
                {p.product_name}: ₹{Number(p.current_price).toLocaleString("en-IN")}
                {p.current_price <= p.target_price ? " — target reached 🎉" : ""}
                <span style={{ color: "#777", fontSize: "0.85em" }}>
                  {" "}({new Date(p.last_checked_at).toLocaleString("en-IN")})
                </span>
              </p>
            ))
          )}
        </section>
      </main>
    </div>
  );
}

export default Dashboard;
