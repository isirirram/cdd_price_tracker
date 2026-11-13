
function Signup({ onNavigate }) {
  const handleSubmit = (e) => {
    e.preventDefault();
    alert("Signup successful! Connect backend authentication next.");
    onNavigate("login");
  };

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-icon">
          <span>👤</span>
        </div>

        <h1>Create Account</h1>
        <p>Join Smart Price Tracker today!</p>

        <form onSubmit={handleSubmit}>
          <input
            type="text"
            placeholder="Full Name"
            required
          />

          <input
            type="email"
            placeholder="Email Address"
            required
          />

          <input
            type="password"
            placeholder="Create Password"
            minLength="6"
            required
          />

          <input
            type="password"
            placeholder="Confirm Password"
            minLength="6"
            required
          />

          <button type="submit" className="login-button">
            Sign Up
          </button>
        </form>

        <p className="signup-text">
          Already have an account?{" "}
          <span onClick={() => onNavigate("login")}>
            Sign In
          </span>
        </p>
      </div>
    </div>
  );
}

export default Signup;
