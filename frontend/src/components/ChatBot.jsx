
import { useState, useEffect } from "react";
import { sendChatMessage, getChatStatus } from "../services/api";

function ChatBot() {
  const [isOpen, setIsOpen] = useState(false);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState("offline");

  const [messages, setMessages] = useState([
    {
      role: "assistant",
      content: "Hi! 👋 I'm your Price Tracker Assistant. How can I help you?",
    },
  ]);

  useEffect(() => {
    getChatStatus()
      .then((data) => setMode(data.mode))
      .catch(() => setMode("offline"));
  }, []);

  const handleSend = async (e) => {
    e.preventDefault();
    const userMessage = message.trim();

    if (!userMessage || loading) return;

    const history = messages.slice(1).slice(-20);

    setMessages((prev) => [
      ...prev,
      { role: "user", content: userMessage },
    ]);

    setMessage("");
    setLoading(true);

    try {
      const data = await sendChatMessage(userMessage, history);

      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: data.reply },
      ]);

      setMode(data.mode);

      if (data.actions?.length > 0) {
        window.dispatchEvent(new Event("products-changed"));
        setTimeout(() => {
          window.dispatchEvent(new Event("products-changed"));
        }, 4000);
      }
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "Sorry, something went wrong. Please try again.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="chatbot-container">
      <button
        className="chatbot-toggle"
        onClick={() => setIsOpen(!isOpen)}
      >
        {isOpen ? "✕" : (
          <svg
            viewBox="0 0 40 40"
            width="34"
            height="34"
            fill="none"
            stroke="currentColor"
            strokeWidth="3"
            strokeLinecap="round"
          >
            <path d="M20 3 V13" />
            <path d="M20 27 V37" />
            <path d="M3 20 H13" />
            <path d="M27 20 H37" />
            <path d="M8 8 L15 15" />
            <path d="M25 25 L32 32" />
            <path d="M32 8 L25 15" />
            <path d="M15 25 L8 32" />
          </svg>
        )}
      </button>

      {!isOpen && (
        <div className="chatbot-label">AI Assistant</div>
      )}

      {isOpen && (
        <div className="chatbot-window">
          <div className="chatbot-header">
            <div>
              <h3>Price Tracker Assistant</h3>
              <span>
                {mode === "ai" ? "AI Assistant" : "Offline Assistant"}
              </span>
            </div>
            <button onClick={() => setIsOpen(false)}>✕</button>
          </div>

          <div className="chatbot-messages">
            {messages.map((msg, index) => (
              <div
                key={index}
                className={`chatbot-message ${msg.role}`}
              >
                {msg.content}
              </div>
            ))}

            {loading && (
              <div className="chatbot-message assistant">
                Thinking...
              </div>
            )}
          </div>

          <form className="chatbot-input" onSubmit={handleSend}>
            <input
              type="text"
              placeholder="Ask me anything..."
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              disabled={loading}
            />
            <button type="submit" disabled={loading || !message.trim()}>
              Send
            </button>
          </form>
        </div>
      )}
    </div>
  );
}

export default ChatBot;
