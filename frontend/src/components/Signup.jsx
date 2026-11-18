
function Signup({ onNavigate }) {
  const handleSubmit = (e) => {
    e.preventDefault();

    const form = e.target;
    const fullName = form.fullName.value.trim();
    const email = form.email.value.trim();
    const password = form.password.value;
    const confirmPassword = form.confirmPassword.value;

    if (!fullName || !email || !password || !confirmPassword) {
      alert("Please fill in all fields.");
      return;
    }

    if (password.length < 6) {
      alert("Password must contain at least 6 characters.");
      return;
    }

    if (password !== confirmPassword) {
      alert("Passwords do not match!");
      return;
    }

    // Demo signup (backend registration is not connected)
    alert("Signup successful! You can now continue to the Dashboard.");
    onNavigate("dashboard");
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
            name="fullName"
            placeholder="Full Name"
            required
          />

          <input
            type="email"
            name="email"
            placeholder="Email Address"
            required
          />

          <input
            type="password"
            name="password"
            placeholder="Create Password"
            minLength="6"
            required
          />

          <input
            type="password"
            name="confirmPassword"
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
