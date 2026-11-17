import { useEffect, useState } from "react";
import {
  getProducts,
  addProduct,
  deleteProduct,
  checkProductNow,
} from "../services/api";
import Header from "./Header";
import AddProduct from "./AddProduct";
import ProductCard from "./ProductCard";

function ProductList({ onNavigate }) {
  const [products, setProducts] = useState([]);
  const [search, setSearch] = useState("");
  const [siteFilter, setSiteFilter] = useState("All");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showAddForm, setShowAddForm] = useState(false);
  const [checkingId, setCheckingId] = useState(null);

  // Only sets state after the request finishes (keeps the linter happy)
  const loadProducts = () =>
    getProducts()
      .then((data) => {
        setProducts(data);
        setError("");
      })
      .catch((err) => setError(err.message || "Unable to load products."))
      .finally(() => setLoading(false));

  useEffect(() => {
    loadProducts();
    // the chat assistant fires this after adding a product
    window.addEventListener("products-changed", loadProducts);
    return () => window.removeEventListener("products-changed", loadProducts);
  }, []);

  const handleRetry = () => {
    setLoading(true);
    loadProducts();
  };

  const handleAdd = async (product) => {
    // Errors are shown inside the AddProduct form
    const created = await addProduct(product);
    setProducts((previous) => [created, ...previous]);
    setShowAddForm(false);

    // The worker fetches the first price in the background; refresh shortly
    setTimeout(loadProducts, 4000);
  };

  const handleCheckNow = async (id) => {
    try {
      setCheckingId(id);
      await checkProductNow(id);
      // give the worker a moment, then reload the new price
      setTimeout(() => {
        loadProducts();
        setCheckingId(null);
      }, 3000);
    } catch (err) {
      setCheckingId(null);
      alert(err.message || "Unable to check price.");
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm("Are you sure you want to remove this product?")) return;

    try {
      await deleteProduct(id);
      setProducts((previous) => previous.filter((p) => p.id !== id));
    } catch (err) {
      alert(err.message || "Unable to delete product.");
    }
  };

  const filteredProducts = products.filter((product) => {
    const matchesSearch = product.product_name
      ?.toLowerCase()
      .includes(search.toLowerCase());

    const matchesSite = siteFilter === "All" || product.site === siteFilter;

    return matchesSearch && matchesSite;
  });

  return (
    <div className="dashboard-page">
      <Header onNavigate={onNavigate} active="products" />

      <main className="products-page">
        <div className="welcome-section">
          <h2>My Products</h2>
          <p>Manage and track all your products in one place.</p>
        </div>

        {showAddForm && (
          <AddProduct
            onAddProduct={handleAdd}
            onCancel={() => setShowAddForm(false)}
          />
        )}

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
            onClick={() => setShowAddForm(true)}
          >
            + Add Product
          </button>
        </div>

        {loading && <p>Loading your products...</p>}

        {error && (
          <div>
            <p>{error}</p>
            <button onClick={handleRetry}>Try Again</button>
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
                  <ProductCard
                    key={product.id}
                    product={product}
                    checking={checkingId === product.id}
                    onViewHistory={() => onNavigate("history", product.id)}
                    onCheckNow={() => handleCheckNow(product.id)}
                    onDelete={() => handleDelete(product.id)}
                  />
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
