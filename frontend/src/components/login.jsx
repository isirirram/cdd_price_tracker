
function Login({ onNavigate }) {
  const handleSubmit = (e) => {
    e.preventDefault();

    const form = e.target;
    const email = form.email.value.trim();
    const password = form.password.value;

    if (!email || !password) {
      alert("Please enter your email and password.");
      return;
    }

    // Demo login (backend authentication is not connected)
    onNavigate("dashboard");
  };

  const handleGoogleLogin = () => {
    alert("Google login is not configured yet.");
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
            name="email"
            placeholder="Email Address"
            required
          />

          <input
            type="password"
            name="password"
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

        <button
          className="google-button"
          type="button"
          onClick={handleGoogleLogin}
        >
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
