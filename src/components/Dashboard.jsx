
function Dashboard({ onNavigate }) {
  const products = [
    {
      name: "Wireless Headphones",
      image: "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=500",
      currentPrice: "1,499",
      targetPrice: "1,200",
      status: "Price Drop Expected",
    },
    {
      name: "Smart Watch",
      image: "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=500",
      currentPrice: "2,499",
      targetPrice: "2,000",
      status: "Tracking",
    },
    {
      name: "Laptop",
      image: "https://images.unsplash.com/photo-1496181133206-80ce9b88a853?w=500",
      currentPrice: "45,999",
      targetPrice: "42,000",
      status: "Tracking",
    },
  ];

  return (
    <div className="dashboard-page">
      <header className="navbar">
        <h1 className="logo">PRICE TRACKER</h1>
        <nav>
  <span onClick={() => onNavigate("dashboard")}>Dashboard</span>
  <span onClick={() => onNavigate("products")}>My Products</span>
  <span onClick={() => onNavigate("history")}>Price History</span>
  <span onClick={() => onNavigate("budget")}>Budget Tracker</span>
  <span onClick={() => onNavigate("profile")}>Profile</span>
</nav>
      </header>

      <main className="dashboard-content">
        <section className="welcome-section">
          <h2>Welcome</h2>
          <p>Track prices, discover deals and save money on your favourite products</p>
        </section>

        <section className="stats-container">
          <div className="stat-card">
            <h3>Tracked Products</h3>
            <h2>12</h2>
          </div>
          <div className="stat-card">
            <h3>Price Drops</h3>
            <h2>3</h2>
          </div>
          <div className="stat-card">
            <h3>Alerts</h3>
            <h2>5</h2>
          </div>
        </section>

        <section className="tracked-section">
          <div className="section-heading">
            <h2>Your Tracked Products</h2>
            <button onClick={() => onNavigate("products")}>
              + Add Product
            </button>
          </div>

          <div className="product-container">
            {products.map((product, index) => (
              <div className="product-card" key={index}>
                <img
                  src={product.image}
                  alt={product.name}
                  className="product-image"
                />

                <h3>{product.name}</h3>
                <p>Current Price: ₹{product.currentPrice}</p>
                <p>Target Price: ₹{product.targetPrice}</p>
                <p>Status: {product.status}</p>

                <button onClick={() => onNavigate("history")}>
                  View Price History
                </button>
              </div>
            ))}
          </div>

          <p className="view-all" onClick={() => onNavigate("products")}>
            View All Products →
          </p>
        </section>

        <section className="activity-section">
          <h2>Recent Activity</h2>
          <p>Price dropped for wireless headphones</p>
        </section>
      </main>
    </div>
  );
}

export default Dashboard;
