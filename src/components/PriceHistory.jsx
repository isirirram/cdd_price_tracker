
import { useEffect, useState } from "react";
import {
  getProducts,
  getPriceHistory,
  getProductInsights,
  getProductDrops,
} from "../services/api";

function PriceHistory({ onNavigate }) {
  const [products, setProducts] = useState([]);
  const [selectedProduct, setSelectedProduct] = useState(null);

  const [history, setHistory] = useState([]);
  const [insights, setInsights] = useState(null);
  const [dropReport, setDropReport] = useState(null);

  const [loading, setLoading] = useState(true);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const fetchProducts = async () => {
      try {
        setLoading(true);
        setError("");

        const data = await getProducts();
        setProducts(data);
      } catch (err) {
        setError(err.message || "Unable to load products.");
      } finally {
        setLoading(false);
      }
    };

    fetchProducts();
  }, []);

  const selectProduct = async (product) => {
    try {
      setSelectedProduct(product);
      setDetailsLoading(true);
      setError("");

      setHistory([]);
      setInsights(null);
      setDropReport(null);

      const [historyData, insightsData, dropsData] =
        await Promise.all([
          getPriceHistory(product.id),
          getProductInsights(product.id),
          getProductDrops(product.id),
        ]);

      setHistory(historyData);
      setInsights(insightsData);
      setDropReport(dropsData);
    } catch (err) {
      setError(err.message || "Unable to load product details.");
    } finally {
      setDetailsLoading(false);
    }
  };

  const formatDate = (date) => {
    return new Date(date).toLocaleDateString("en-IN", {
      day: "2-digit",
      month: "short",
    });
  };

  const formatPrice = (price) => {
    return `₹${Number(price).toLocaleString("en-IN")}`;
  };

  // Graph calculations
  const chartWidth = 760;
  const chartHeight = 300;

  const chartLeft = 75;
  const chartRight = 25;
  const chartTop = 25;
  const chartBottom = 55;

  const chartAreaWidth = chartWidth - chartLeft - chartRight;
  const chartAreaHeight = chartHeight - chartTop - chartBottom;

  const prices = history.map((item) => Number(item.price));

  const minPrice = prices.length ? Math.min(...prices) : 0;
  const maxPrice = prices.length ? Math.max(...prices) : 0;

  const priceRange = maxPrice - minPrice || 1;

  const points = history.map((item, index) => {
    const x =
      chartLeft +
      (history.length === 1
        ? chartAreaWidth / 2
        : (index / (history.length - 1)) * chartAreaWidth);

    const y =
      chartTop +
      ((maxPrice - Number(item.price)) / priceRange) *
        chartAreaHeight;

    return {
      x,
      y,
      price: item.price,
      date: item.checked_at,
    };
  });

  const graphLine = points
    .map((point, index) =>
      `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`
    )
    .join(" ");

  const yLabels = Array.from({ length: 5 }, (_, index) => {
    return maxPrice - (index / 4) * priceRange;
  });

  const recommendationColor = {
    buy_now: "#2E7D32",
    wait: "#E35336",
    neutral: "#A0522D",
    not_enough_data: "#777777",
  };

  const recommendationText = {
    buy_now: "Buy Now",
    wait: "Wait",
    neutral: "Neutral",
    not_enough_data: "Not Enough Data",
  };

  return (
    <div className="dashboard-page">
      <header className="navbar">
        <h1 className="logo">PRICE TRACKER</h1>

        <nav>
          <span onClick={() => onNavigate("dashboard")}>Dashboard</span>
          <span onClick={() => onNavigate("products")}>My Products</span>
          <span onClick={() => onNavigate("history")}>Price History</span>
          <span onClick={() => onNavigate("profile")}>Profile</span>
          <span onClick={() => onNavigate("budget")}>Budget Tracker</span>
        </nav>
      </header>

      <main className="history-page">
        <div className="welcome-section">
          <h2>Price History & Insights</h2>
          <p>
            Track price changes and discover the best time to buy.
          </p>
        </div>

        {loading && <p>Loading your products...</p>}

        {error && (
          <div>
            <p>{error}</p>
            <button onClick={() => window.location.reload()}>
              Retry
            </button>
          </div>
        )}

        {!loading && !error && (
          <>
            <h3>Select a Product</h3>

            {products.length === 0 ? (
              <p>No products available. Add a product first.</p>
            ) : (
              <div className="product-grid">
                {products.map((product) => (
                  <div
                    className="product-card"
                    key={product.id}
                    onClick={() => selectProduct(product)}
                    style={{
                      cursor: "pointer",
                      border:
                        selectedProduct?.id === product.id
                          ? "2px solid #A0522D"
                          : "1px solid #ddd",
                    }}
                  >
                    <div className="product-image">
                      <span style={{ fontSize: "50px" }}>🛍️</span>
                    </div>

                    <div className="product-info">
                      <h3>{product.product_name}</h3>

                      <p>
                        Current Price:{" "}
                        <strong>
                          {product.current_price != null
                            ? formatPrice(product.current_price)
                            : "Not available"}
                        </strong>
                      </p>

                      <p style={{ color: "#A0522D" }}>
                        Click to view details
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}

        {detailsLoading && <p>Loading price history and insights...</p>}

        {selectedProduct && !detailsLoading && !error && (
          <>
            <div className="chart-card" style={{ marginTop: "35px" }}>
              <h2>{selectedProduct.product_name}</h2>
              <p>Price History</p>

              {history.length === 0 ? (
                <p>
                  No price history available for this product yet.
                </p>
              ) : (
                <>
                  <div style={{ width: "100%", overflowX: "auto" }}>
                    <svg
                      viewBox={`0 0 ${chartWidth} ${chartHeight}`}
                      style={{ width: "100%", minWidth: "500px" }}
                    >
                      {yLabels.map((price, index) => {
                        const y =
                          chartTop +
                          (index / 4) * chartAreaHeight;

                        return (
                          <g key={index}>
                            <line
                              x1={chartLeft}
                              y1={y}
                              x2={chartWidth - chartRight}
                              y2={y}
                              stroke="#ddd"
                              strokeDasharray="4 4"
                            />

                            <text
                              x={chartLeft - 10}
                              y={y + 5}
                              textAnchor="end"
                              fontSize="12"
                              fill="#555"
                            >
                              ₹{Math.round(price).toLocaleString("en-IN")}
                            </text>
                          </g>
                        );
                      })}

                      <line
                        x1={chartLeft}
                        y1={chartTop}
                        x2={chartLeft}
                        y2={chartHeight - chartBottom}
                        stroke="#555"
                      />

                      <line
                        x1={chartLeft}
                        y1={chartHeight - chartBottom}
                        x2={chartWidth - chartRight}
                        y2={chartHeight - chartBottom}
                        stroke="#555"
                      />

                      <path
                        d={graphLine}
                        fill="none"
                        stroke="#A0522D"
                        strokeWidth="3"
                        strokeLinejoin="round"
                        strokeLinecap="round"
                      />

                      {points.map((point, index) => (
                        <g key={index}>
                          <circle
                            cx={point.x}
                            cy={point.y}
                            r="5"
                            fill="#E35336"
                          />

                          <title>
                            {formatDate(point.date)}:{" "}
                            {formatPrice(point.price)}
                          </title>

                          {(index === 0 ||
                            index === points.length - 1 ||
                            index % Math.ceil(points.length / 6) === 0) && (
                            <text
                              x={point.x}
                              y={chartHeight - chartBottom + 22}
                              textAnchor="middle"
                              fontSize="11"
                              fill="#555"
                            >
                              {formatDate(point.date)}
                            </text>
                          )}
                        </g>
                      ))}

                      <text
                        x="15"
                        y={chartHeight / 2}
                        transform={`rotate(-90 15 ${chartHeight / 2})`}
                        textAnchor="middle"
                        fontSize="12"
                        fill="#555"
                      >
                        Price (₹)
                      </text>

                      <text
                        x={chartWidth / 2}
                        y={chartHeight - 5}
                        textAnchor="middle"
                        fontSize="12"
                        fill="#555"
                      >
                        Date
                      </text>
                    </svg>
                  </div>

                  <div style={{ display: "flex", gap: "20px" }}>
                    <p>
                      <strong>Lowest:</strong> {formatPrice(minPrice)}
                    </p>
                    <p>
                      <strong>Highest:</strong> {formatPrice(maxPrice)}
                    </p>
                  </div>
                </>
              )}
            </div>

            {/* BEST TIME TO BUY */}
            {insights && (
              <div className="chart-card" style={{ marginTop: "25px" }}>
                <h2>Best Time to Buy</h2>

                <h3
                  style={{
                    color:
                      recommendationColor[insights.recommendation],
                    marginTop: "15px",
                  }}
                >
                  {recommendationText[insights.recommendation]}
                </h3>

                <p>{insights.reason}</p>

                <div className="history-grid">
                  <p>
                    <strong>Current Price:</strong>{" "}
                    {insights.current_price != null
                      ? formatPrice(insights.current_price)
                      : "—"}
                  </p>

                  <p>
                    <strong>Lowest Price:</strong>{" "}
                    {insights.lowest_price != null
                      ? formatPrice(insights.lowest_price)
                      : "—"}
                  </p>

                  <p>
                    <strong>Average Price:</strong>{" "}
                    {insights.average_price != null
                      ? formatPrice(insights.average_price)
                      : "—"}
                  </p>

                  <p>
                    <strong>Highest Price:</strong>{" "}
                    {insights.highest_price != null
                      ? formatPrice(insights.highest_price)
                      : "—"}
                  </p>

                  <p>
                    <strong>Moving Average (7):</strong>{" "}
                    {insights.moving_average_7 != null
                      ? formatPrice(insights.moving_average_7)
                      : "—"}
                  </p>

                  <p>
                    <strong>Confidence:</strong>{" "}
                    {insights.confidence}
                  </p>
                </div>

                {insights.best_time_to_buy && (
                  <div>
                    <h3>Cheapest Buying Periods</h3>

                    <p>
                      <strong>Cheapest week of month:</strong>{" "}
                      {insights.best_time_to_buy.cheapest_week_of_month
                        ? `Week ${insights.best_time_to_buy.cheapest_week_of_month.bucket}`
                        : "Not enough data"}
                    </p>

                    <p>
                      <strong>Cheapest weekday:</strong>{" "}
                      {insights.best_time_to_buy.cheapest_weekday
                        ? insights.best_time_to_buy.cheapest_weekday.bucket
                        : "Not enough data"}
                    </p>
                  </div>
                )}

                {insights.active_sale_event && (
                  <p>
                    <strong>Active Sale:</strong>{" "}
                    {insights.active_sale_event}
                  </p>
                )}

                {insights.sale_note && <p>{insights.sale_note}</p>}

                <small>{insights.disclaimer}</small>
              </div>
            )}

            {/* SALE EVENT TRACKER */}
            {dropReport && (
              <div className="chart-card" style={{ marginTop: "25px" }}>
                <h2>Festival & Sale Price Drops</h2>

                <div className="history-grid">
                  <p>
                    <strong>Sale Event Drops:</strong>{" "}
                    {dropReport.summary.sale_event_drops}
                  </p>

                  <p>
                    <strong>Standalone Drops:</strong>{" "}
                    {dropReport.summary.standalone_drops}
                  </p>

                  <p>
                    <strong>Average Sale Drop:</strong>{" "}
                    {dropReport.summary.average_sale_drop_percent != null
                      ? `${dropReport.summary.average_sale_drop_percent}%`
                      : "—"}
                  </p>

                  <p>
                    <strong>Average Standalone Drop:</strong>{" "}
                    {dropReport.summary.average_standalone_drop_percent != null
                      ? `${dropReport.summary.average_standalone_drop_percent}%`
                      : "—"}
                  </p>
                </div>

                {dropReport.summary.currently_in_sale_event && (
                  <p>
                    <strong>Current Event:</strong>{" "}
                    {dropReport.summary.currently_in_sale_event}
                  </p>
                )}

                {dropReport.drops.length === 0 ? (
                  <p>No significant price drops detected yet.</p>
                ) : (
                  <div style={{ overflowX: "auto" }}>
                    <table style={{ width: "100%", textAlign: "left" }}>
                      <thead>
                        <tr>
                          <th>Date</th>
                          <th>Previous Price</th>
                          <th>New Price</th>
                          <th>Drop</th>
                          <th>Classification</th>
                        </tr>
                      </thead>

                      <tbody>
                        {dropReport.drops.map((drop, index) => (
                          <tr key={index}>
                            <td>{formatDate(drop.detected_at)}</td>
                            <td>{formatPrice(drop.from_price)}</td>
                            <td>{formatPrice(drop.to_price)}</td>
                            <td>{drop.drop_percent}%</td>
                            <td>
                              {drop.classification === "sale_event"
                                ? `🎉 ${drop.sale_event}`
                                : "Standalone"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}

export default PriceHistory;
