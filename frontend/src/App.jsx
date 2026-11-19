import { useState } from "react";

import Dashboard from "./components/Dashboard";
import ProductList from "./components/ProductList";
import PriceHistory from "./components/PriceHistory";
import BudgetTracker from "./components/BudgetTracker";
import ChatBot from "./components/ChatBot";

// Single-user app: it opens straight on the dashboard.
// User accounts (sign up / login) are planned future work.
function App() {
  const [currentPage, setCurrentPage] = useState("dashboard");
  // Lets "View Price History" on a product open that product directly
  const [selectedProductId, setSelectedProductId] = useState(null);

  const navigate = (page, productId = null) => {
    setSelectedProductId(productId);
    setCurrentPage(page);
  };

  return (
    <>
      {currentPage === "dashboard" && <Dashboard onNavigate={navigate} />}

      {currentPage === "products" && <ProductList onNavigate={navigate} />}

      {currentPage === "history" && (
        <PriceHistory
          onNavigate={navigate}
          initialProductId={selectedProductId}
        />
      )}

      {currentPage === "budget" && <BudgetTracker onNavigate={navigate} />}

      {/* AI assistant on every page */}
      <ChatBot />
    </>
  );
}

export default App;
