
function Header({ onNavigate }) {
  return (
    <header className="navbar">
      <h1
        className="logo"
        onClick={() => onNavigate("dashboard")}
      >
        PRICE TRACKER
      </h1>

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

        <span onClick={() => onNavigate("profile")}>
          Profile
        </span>
      </nav>
    </header>
  );
}

export default Header;
