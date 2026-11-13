
function Header({ onNavigate }) {
  return (
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

        <span>Profile</span>
      </nav>

      <span onClick={() => onNavigate("budget")}>Budget Tracker</span>
    </header>
  );
}

export default Header;
