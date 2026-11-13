
function Login({ onNavigate }) {
  const handleSubmit = (e) => {
    e.preventDefault();
    onNavigate("dashboard");
  };

  return (
    <div className="login-page">
      <div className="login-card">

        <div className="login-icon">
          <span>👤</span>
        </div>

        <h1>Sign In</h1>
        <p>Welcome back to Smart Price Tracker!</p>

        <form onSubmit={handleSubmit}>
          <input
            type="email"
            placeholder="Email Address"
            required
          />

          <input
            type="password"
            placeholder="Password"
            required
          />

          <p className="forgot-password">
            Forgot Password?
          </p>

          <button type="submit" className="login-button">
            Sign In
          </button>
        </form>

        <div className="login-divider">
          <span></span>
          <p>or</p>
          <span></span>
        </div>

        <button className="google-button" type="button">
          Continue with Google
        </button>

        <p className="signup-text">
          Don't have an account?{" "}
          <span onClick={() => onNavigate("signup")}>
            Signup
          </span>
        </p>

      </div>
    </div>
  );
}

export default Login;
