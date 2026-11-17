import { useState } from "react";

import Login from "./components/login";
import Signup from "./components/Signup";
import Dashboard from "./components/Dashboard";
import ProductList from "./components/ProductList";
import PriceHistory from "./components/PriceHistory";
import Profile from "./components/Profile";
import BudgetTracker from "./components/BudgetTracker";

function App() {
  const [currentPage, setCurrentPage] = useState("login");
  // Lets "View Price History" on a product open that product directly
  const [selectedProductId, setSelectedProductId] = useState(null);

  const navigate = (page, productId = null) => {
    setSelectedProductId(productId);
    setCurrentPage(page);
  };

  return (
    <>
      {currentPage === "login" && <Login onNavigate={navigate} />}

      {currentPage === "signup" && <Signup onNavigate={navigate} />}

      {currentPage === "dashboard" && <Dashboard onNavigate={navigate} />}

      {currentPage === "products" && <ProductList onNavigate={navigate} />}

      {currentPage === "history" && (
        <PriceHistory
          onNavigate={navigate}
          initialProductId={selectedProductId}
        />
      )}

      {currentPage === "budget" && <BudgetTracker onNavigate={navigate} />}

      {currentPage === "profile" && <Profile onNavigate={navigate} />}
    </>
  );
}

export default App;
