const LINKS = [
  ["dashboard", "Dashboard"],
  ["products", "My Products"],
  ["history", "Price History"],
  ["budget", "Budget Tracker"],
];

// Shared navbar used by every page
function Header({ onNavigate, active }) {
  return (
    <header className="navbar">
      <h1 className="logo">PRICE TRACKER</h1>

      <nav>
        {LINKS.map(([page, label]) => (
          <span
            key={page}
            onClick={() => onNavigate(page)}
            style={active === page ? { textDecoration: "underline" } : undefined}
          >
            {label}
          </span>
        ))}
      </nav>
    </header>
  );
}

export default Header;
