import Header from "./Header";

function Profile({ onNavigate }) {
  return (
    <div className="dashboard-page">
      <Header onNavigate={onNavigate} active="profile" />

      <main className="dashboard-content">
        <section className="welcome-section">
          <h2>My Profile</h2>
          <p>Manage your account information</p>
        </section>

        <div className="login-card profile-card">
          <div className="login-icon">
            <span>👤</span>
          </div>

          <h2>Personal Information</h2>

          <form onSubmit={(e) => e.preventDefault()}>
            <label>Full Name</label>
            <input type="text" placeholder="Enter your name" />

            <label>Email Address</label>
            <input type="email" placeholder="Enter your email" />

            <label>Phone Number</label>
            <input type="tel" placeholder="Enter phone number" />

            <button type="submit" className="login-button">
              Save Changes
            </button>
          </form>

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
