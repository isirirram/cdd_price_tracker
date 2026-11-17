import { useEffect, useRef, useState } from "react";
import { sendChatMessage, getChatStatus } from "../services/api";

const SUGGESTIONS = [
  "Should I buy now?",
  "What fits my budget?",
  "Show my products",
];

const WELCOME = {
  role: "assistant",
  content:
    "Hi! I'm your price assistant. Ask me whether to buy something now, what fits your budget, or paste a product link with a target price and I'll start tracking it.",
};

// Tiny formatter for **bold** and _italic_ in bot replies (no HTML injection)
function renderInline(text) {
  return text.split(/(\*\*[^*]+\*\*|_[^_]+_)/g).map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={i}>{part.slice(2, -2)}</strong>;
    }
    if (part.length > 2 && part.startsWith("_") && part.endsWith("_")) {
      return <em key={i}>{part.slice(1, -1)}</em>;
    }
    return part;
  });
}

function ChatBot() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([WELCOME]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [mode, setMode] = useState(null);
  const bottomRef = useRef(null);

  useEffect(() => {
    getChatStatus()
      .then((s) => setMode(s.mode))
      .catch(() => setMode(null));
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, open]);

  const send = async (text) => {
    const message = text.trim();
    if (!message || sending) return;

    // history = previous turns, without the welcome message
    const history = messages.slice(1);
    setMessages((prev) => [...prev, { role: "user", content: message }]);
    setInput("");
    setSending(true);

    try {
      const res = await sendChatMessage(message, history);
      setMessages((prev) => [...prev, { role: "assistant", content: res.reply }]);
      setMode(res.mode);

      // Let product pages refresh when the bot added a product or queued a check
      if (res.actions?.length) {
        window.dispatchEvent(new Event("products-changed"));
        setTimeout(() => window.dispatchEvent(new Event("products-changed")), 4000);
      }
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: `Sorry, something went wrong: ${err.message}` },
      ]);
    } finally {
      setSending(false);
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    send(input);
  };

  if (!open) {
    return (
      <button className="chatbot-toggle" onClick={() => setOpen(true)} aria-label="Open price assistant">
        💬
      </button>
    );
  }

  return (
    <div className="chatbot-panel">
      <div className="chatbot-header">
        <div>
          <strong>Price Assistant</strong>
          {mode && (
            <span className="chatbot-mode">{mode === "ai" ? "AI" : "offline mode"}</span>
          )}
        </div>
        <button onClick={() => setOpen(false)} aria-label="Close">✕</button>
      </div>

      <div className="chatbot-messages">
        {messages.map((m, i) => (
          <div key={i} className={`chatbot-bubble ${m.role}`}>
            {m.content.split("\n").map((line, j) => (
              <div key={j}>{renderInline(line)}</div>
            ))}
          </div>
        ))}
        {sending && <div className="chatbot-bubble assistant">Thinking…</div>}
        <div ref={bottomRef} />
      </div>

      {messages.length === 1 && (
        <div className="chatbot-suggestions">
          {SUGGESTIONS.map((s) => (
            <button key={s} onClick={() => send(s)}>
              {s}
            </button>
          ))}
        </div>
      )}

      <form className="chatbot-input" onSubmit={handleSubmit}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about a product or paste a link…"
          maxLength={1000}
          disabled={sending}
        />
        <button type="submit" disabled={sending || !input.trim()}>
          Send
        </button>
      </form>
    </div>
  );
}

export default ChatBot;
