
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

  const navigate = (page) => {
    setCurrentPage(page);
  };

  return (
    <>
      {currentPage === "login" && (
        <Login onNavigate={navigate} />
      )}

      {currentPage === "signup" && (
        <Signup onNavigate={navigate} />
      )}

      {currentPage === "dashboard" && (
        <Dashboard onNavigate={navigate} />
      )}

      {currentPage === "products" && (
        <ProductList onNavigate={navigate} />
      )}

      {currentPage === "history" && (
        <PriceHistory onNavigate={navigate} />
      )}

      {currentPage === "budget" && (
        <BudgetTracker onNavigate={navigate} />
      )}

      {currentPage === "profile" && (
        <Profile onNavigate={navigate} />
      )}
    </>
  );
}

export default App;
