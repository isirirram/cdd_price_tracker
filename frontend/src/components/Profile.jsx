
function Profile({ onNavigate }) {
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

      <main className="dashboard-content">
        <section className="welcome-section">
          <h2>My Profile</h2>
          <p>Manage your account information and notification preferences.</p>
        </section>

        <div className="login-card profile-card">
          <div className="login-icon">
            <span>👤</span>
          </div>

          <h2>Personal Information</h2>

          <form onSubmit={(e) => e.preventDefault()}>
            <label>Full Name</label>
            <input
              type="text"
              placeholder="Enter your name"
            />

            <label>Email Address</label>
            <input
              type="email"
              placeholder="Enter your email"
            />

            <label>Phone Number</label>
            <input
              type="tel"
              placeholder="Enter phone number"
            />

            <button type="submit" className="login-button">
              Save Changes
            </button>
          </form>

          <div className="notification-info">
            <h2>Notification Information</h2>

            <p>
              <strong>Email Alerts</strong>
            </p>

            <p>
              Enter your email address while adding a product
              to receive an alert when its target price is reached.
            </p>

            <p>
              <strong>Telegram Alerts</strong>
            </p>

            <p>
              Telegram notifications depend on the bot configuration
              in the backend.
            </p>
          </div>

          <button
            className="google-button"
            onClick={() => onNavigate("login")}
          >
            Logout
          </button>
        </div>
      </main>
    </div>
  );
}

export default Profile;
