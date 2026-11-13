
import { useEffect, useState } from "react";
import { getProducts, deleteProduct } from "../services/api";

function ProductList({ onNavigate }) {
  const [products, setProducts] = useState([]);
  const [search, setSearch] = useState("");
  const [siteFilter, setSiteFilter] = useState("All");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const fetchProducts = async () => {
    try {
      setLoading(true);
      setError("");

      const data = await getProducts();
      setProducts(data);
    } catch (err) {
      setError(err.message || "Unable to load products.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProducts();
  }, []);

  const handleDelete = async (id) => {
    const confirmDelete = window.confirm(
      "Are you sure you want to remove this product?"
    );

    if (!confirmDelete) return;

    try {
      await deleteProduct(id);
      setProducts((previous) =>
        previous.filter((product) => product.id !== id)
      );
    } catch (err) {
      alert(err.message || "Unable to delete product.");
    }
  };

  const filteredProducts = products.filter((product) => {
    const matchesSearch = product.product_name
      ?.toLowerCase()
      .includes(search.toLowerCase());

    const matchesSite =
      siteFilter === "All" || product.site === siteFilter;

    return matchesSearch && matchesSite;
  });

  return (
    <div className="dashboard-page">
      <header className="navbar">
        <h1 className="logo">PRICE TRACKER</h1>

        <nav>
          <span onClick={() => onNavigate("dashboard")}>Dashboard</span>
          <span onClick={() => onNavigate("products")}>My Products</span>
          <span onClick={() => onNavigate("history")}>Price History</span>
          <span onClick={() => onNavigate("profile")}>Profile</span>
          <span onClick={() => onNavigate("budget")}>Budget Tracker</span>
        </nav>
      </header>

      <main className="products-page">
        <div className="welcome-section">
          <h2>My Products</h2>
          <p>Manage and track all your products in one place.</p>
        </div>

        <div className="product-controls">
          <input
            type="text"
            placeholder="Search products..."
            className="search-input"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />

          <select
            className="category-filter"
            value={siteFilter}
            onChange={(e) => setSiteFilter(e.target.value)}
          >
            <option value="All">All Websites</option>
            <option value="amazon">Amazon</option>
            <option value="flipkart">Flipkart</option>
            <option value="other">Other</option>
          </select>

          <button
            className="add-product-button"
            onClick={() => alert("We'll connect Add Product next!")}
          >
            + Add Product
          </button>
        </div>

        {loading && <p>Loading your products...</p>}

        {error && (
          <div>
            <p>{error}</p>
            <button onClick={fetchProducts}>Try Again</button>
          </div>
        )}

        {!loading && !error && (
          <>
            <p className="product-count">
              {filteredProducts.length} product(s) found
            </p>

            {filteredProducts.length === 0 ? (
              <div className="welcome-section">
                <h3>No products found</h3>
                <p>Add a product to start tracking its price.</p>
              </div>
            ) : (
              <div className="product-grid">
                {filteredProducts.map((product) => (
                  <div className="product-card" key={product.id}>
                    <div className="product-image">
                      <span style={{ fontSize: "55px" }}>🛍️</span>
                    </div>

                    <div className="product-info">
                      <p className="product-category">
                        {product.site?.toUpperCase()}
                      </p>

                      <h3>{product.product_name}</h3>

                      <p>
                        Current Price:{" "}
                        <strong>
                          {product.current_price != null
                            ? `₹${product.current_price}`
                            : "Not checked yet"}
                        </strong>
                      </p>

                      <p>
                        Target Price:{" "}
                        <strong>₹{product.target_price}</strong>
                      </p>

                      <button
                        className="view-history-button"
                        onClick={() => onNavigate("history")}
                      >
                        View Price History
                      </button>

                      <button
                        className="add-product-button"
                        onClick={() => handleDelete(product.id)}
                      >
                        Remove Product
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}

export default ProductList;
