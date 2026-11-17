
import { useState } from "react";
import { setBudget, getBudgetPlan } from "../services/api";
import Header from "./Header";

function BudgetTracker({ onNavigate }) {
  const [budget, setBudgetValue] = useState("");
  const [spent, setSpent] = useState("0");
  const [plan, setPlan] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (Number(budget) <= 0 || Number(spent) < 0) {
      setError("Please enter valid budget amounts.");
      return;
    }

    if (Number(spent) > Number(budget)) {
      setError("Amount spent cannot exceed your monthly budget.");
      return;
    }

    try {
      setLoading(true);
      setError("");
      setPlan(null);

      await setBudget(Number(budget), Number(spent));

      const result = await getBudgetPlan();
      setPlan(result);
    } catch (err) {
      setError(err.message || "Unable to update budget.");
    } finally {
      setLoading(false);
    }
  };

  const formatPrice = (price) => {
    if (price === null || price === undefined) return "—";

    return `₹${Number(price).toLocaleString("en-IN")}`;
  };

  const recommended = plan?.recommended || [];
  const skipped = plan?.skipped || [];
  const waiting = plan?.waiting_for_first_price || [];

  return (
    <div className="dashboard-page">
      <Header onNavigate={onNavigate} active="budget" />

      <main className="history-page">
        <div className="welcome-section">
          <h2>Monthly Budget Tracker</h2>
          <p>
            Set your budget and discover the best deals within it.
          </p>
        </div>

        <div className="chart-card">
          <h2>Set Your Monthly Budget</h2>

          <form onSubmit={handleSubmit}>
            <label>Monthly Budget (₹)</label>

            <input
              type="number"
              min="1"
              step="0.01"
              placeholder="Enter your monthly budget"
              value={budget}
              onChange={(e) => setBudgetValue(e.target.value)}
              required
            />

            <label>Amount Already Spent (₹)</label>

            <input
              type="number"
              min="0"
              step="0.01"
              placeholder="Enter amount spent"
              value={spent}
              onChange={(e) => setSpent(e.target.value)}
              required
            />

            <button
              type="submit"
              className="add-product-button"
              disabled={loading}
            >
              {loading ? "Calculating..." : "Save Budget & Find Deals"}
            </button>
          </form>

          {error && (
            <p style={{ color: "#E35336", marginTop: "15px" }}>
              {error}
            </p>
          )}
        </div>

        {plan && (
          <>
            <div className="history-grid" style={{ marginTop: "25px" }}>
              <div className="chart-card">
                <h3>Monthly Budget</h3>
                <h2>{formatPrice(plan.monthly_budget)}</h2>
              </div>

              <div className="chart-card">
                <h3>Budget Remaining</h3>
                <h2>{formatPrice(plan.budget_left)}</h2>
              </div>

              <div className="chart-card">
                <h3>Recommended Deals Total</h3>
                <h2>{formatPrice(plan.recommended_total)}</h2>
              </div>

              <div className="chart-card">
                <h3>Remaining After Deals</h3>
                <h2>{formatPrice(plan.left_after_recommended)}</h2>
              </div>
            </div>

            <div className="chart-card" style={{ marginTop: "25px" }}>
              <h2>Best Deals Within Your Budget 🎉</h2>

              {recommended.length === 0 ? (
                <p>
                  No suitable deals found within your remaining budget.
                </p>
              ) : (
                recommended.map((product) => (
                  <div
                    key={product.product_id}
                    className="alert-card"
                    style={{ marginTop: "15px" }}
                  >
                    <h3>{product.product_name}</h3>

                    <p>
                      Current Price:{" "}
                      <strong>{formatPrice(product.current_price)}</strong>
                    </p>

                    <p>
                      Average Price: {formatPrice(product.average_price)}
                    </p>

                    <p>
                      Deal Score:{" "}
                      <strong style={{ color: "#2E7D32" }}>
                        {product.deal_score_percent}% lower
                      </strong>
                    </p>

                    <p>
                      Target Price Hit: {product.target_hit ? "Yes ✓" : "No"}
                    </p>
                  </div>
                ))
              )}
            </div>

            <div className="chart-card" style={{ marginTop: "25px" }}>
              <h2>Other Products</h2>

              {skipped.length === 0 ? (
                <p>No skipped products.</p>
              ) : (
                skipped.map((product) => (
                  <div
                    key={product.product_id}
                    className="alert-card"
                    style={{ marginTop: "15px" }}
                  >
                    <h3>{product.product_name}</h3>

                    <p>
                      Current Price: {formatPrice(product.current_price)}
                    </p>

                    <p>
                      Reason:{" "}
                      {product.reason === "over_budget"
                        ? "Exceeds remaining budget"
                        : "No price drop compared with average"}
                    </p>
                  </div>
                ))
              )}

              {waiting.length > 0 && (
                <>
                  <h3 style={{ marginTop: "20px" }}>
                    Waiting for First Price Check
                  </h3>

                  {waiting.map((product) => (
                    <p key={product.product_id}>
                      {product.product_name}
                    </p>
                  ))}
                </>
              )}
            </div>
          </>
        )}
      </main>
    </div>
  );
}

export default BudgetTracker;
