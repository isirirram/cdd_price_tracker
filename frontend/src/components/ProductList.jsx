
import { useEffect, useState } from "react";
import { getProducts, deleteProduct } from "../services/api";
import AddProduct from "./AddProduct";

function ProductList({ onNavigate }) {
  const [products, setProducts] = useState([]);
  const [search, setSearch] = useState("");
  const [siteFilter, setSiteFilter] = useState("All");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showAddProduct, setShowAddProduct] = useState(false);
  const [adding, setAdding] = useState(false);

  const fetchProducts = async () => {
    try {
      setLoading(true);
      setError("");

      const data = await getProducts();
      setProducts(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(err.message || "Unable to load products.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProducts();

    const handleProductsChanged = () => {
      fetchProducts();
    };

    window.addEventListener("products-changed", handleProductsChanged);

    return () => {
      window.removeEventListener(
        "products-changed",
        handleProductsChanged
      );
    };
  }, []);

  const handleAddProduct = async (productData) => {
    try {
      setAdding(true);
      setError("");

      const { addProduct } = await import("../services/api");
      await addProduct(productData);

      setShowAddProduct(false);
      await fetchProducts();

      window.dispatchEvent(new Event("products-changed"));
    } catch (err) {
      setError(err.message || "Unable to add product.");
    } finally {
      setAdding(false);
    }
  };

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

      window.dispatchEvent(new Event("products-changed"));
    } catch (err) {
      alert(err.message || "Unable to remove product.");
    }
  };

  const filteredProducts = products.filter((product) => {
    const matchesSearch = product.product_name
      ?.toLowerCase()
      .includes(search.toLowerCase());

    const matchesSite =
      siteFilter === "All" ||
      product.site?.toLowerCase() === siteFilter.toLowerCase();

    return matchesSearch && matchesSite;
  });

  // Automatically get all available website names
  const availableSites = [
    ...new Set(
      products
        .map((product) => product.site)
        .filter(Boolean)
    ),
  ].sort();

  if (showAddProduct) {
    return (
      <AddProduct
        onAddProduct={handleAddProduct}
        onCancel={() => setShowAddProduct(false)}
      />
    );
  }

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

            {availableSites.map((site) => (
              <option key={site} value={site}>
                {site}
              </option>
            ))}
          </select>

          <button
            className="add-product-button"
            onClick={() => setShowAddProduct(true)}
          >
            + Add Product
          </button>
        </div>

        {adding && (
          <p>Adding product and fetching details...</p>
        )}

        {loading && <p>Loading your products...</p>}

        {error && (
          <div>
            <p>{error}</p>
            <button onClick={fetchProducts}>
              Try Again
            </button>
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
                <p>
                  Add a product to start tracking its price.
                </p>
              </div>
            ) : (
              <div className="product-grid">
                {filteredProducts.map((product) => (
                  <div className="product-card" key={product.id}>
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
                        <span style={{ fontSize: "55px" }}>
                          📦
                        </span>
                      )}
                    </div>

                    <div className="product-info">
                      <p className="product-category">
                        {product.site?.toUpperCase() ||
                          "UNKNOWN STORE"}
                      </p>

                      <h3>
                        {product.product_name ||
                          "Product name unavailable"}
                      </h3>

                      <p>
                        Current Price:{" "}
                        <strong>
                          {product.current_price != null
                            ? `₹${Number(
                                product.current_price
                              ).toLocaleString("en-IN")}`
                            : "Waiting for price check"}
                        </strong>
                      </p>

                      <p>
                        Target Price:{" "}
                        <strong>
                          ₹
                          {Number(
                            product.target_price
                          ).toLocaleString("en-IN")}
                        </strong>
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
