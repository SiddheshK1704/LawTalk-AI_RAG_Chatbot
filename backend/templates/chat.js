const chatForm = document.getElementById("chat-form");
const messageInput = document.getElementById("message-input");
const chatMessages = document.getElementById("chat-messages");
const sendButton = document.getElementById("send-button");
const statusText = document.getElementById("status-text");
const modeButtons = document.querySelectorAll(".mode-toggle");

let currentMode = "rag";

function setStatus(text) {
  statusText.textContent = text;
}

function formatModeLabel(mode) {
  return mode === "groq" ? "Groq LLM" : "RAG";
}

function updateModeButtons() {
  modeButtons.forEach((button) => {
    const isActive = button.dataset.mode === currentMode;
    button.setAttribute("aria-pressed", String(isActive));
    button.className = isActive
      ? "mode-toggle rounded-full bg-sky-400 px-4 py-2 text-sm font-semibold text-slate-950 transition"
      : "mode-toggle rounded-full px-4 py-2 text-sm font-semibold text-slate-300 transition hover:text-white";
  });
}

function appendMessage(role, text) {
  const article = document.createElement("article");
  const isUser = role === "user";

  article.className = isUser
    ? "ml-auto max-w-3xl rounded-3xl border border-amber-300/20 bg-amber-300/10 p-4 text-sm leading-7 text-slate-100"
    : "max-w-3xl rounded-3xl border border-sky-400/20 bg-sky-400/10 p-4 text-sm leading-7 text-slate-100";

  const label = document.createElement("p");
  label.className = isUser
    ? "mb-2 text-xs font-semibold uppercase tracking-[0.3em] text-amber-200"
    : "mb-2 text-xs font-semibold uppercase tracking-[0.3em] text-sky-300";
  label.textContent = isUser ? "You" : "LawTalk";

  const content = document.createElement("p");
  content.className = "whitespace-pre-wrap";
  content.textContent = text;

  article.appendChild(label);
  article.appendChild(content);
  chatMessages.appendChild(article);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

async function sendMessage(message, mode) {
  const response = await fetch("/api/chat", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ message, mode }),
  });

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data.error || "Something went wrong.");
  }

  return {
    answer: data.answer || "No response received.",
    mode: data.mode || mode,
  };
}

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const message = messageInput.value.trim();
  if (!message) {
    setStatus("Enter a message");
    return;
  }

  appendMessage("user", message);
  messageInput.value = "";
  messageInput.focus();
  sendButton.disabled = true;
  setStatus(`Thinking with ${formatModeLabel(currentMode)}...`);

  try {
    const result = await sendMessage(message, currentMode);
    appendMessage("assistant", result.answer);
    setStatus(`Ready - ${formatModeLabel(result.mode)} selected`);
  } catch (error) {
    appendMessage("assistant", error.message);
    setStatus("Backend unavailable");
  } finally {
    sendButton.disabled = false;
  }
});

messageInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    chatForm.requestSubmit();
  }
});

modeButtons.forEach((button) => {
  button.addEventListener("click", () => {
    currentMode = button.dataset.mode;
    updateModeButtons();
    setStatus(`Ready - ${formatModeLabel(currentMode)} selected`);
  });
});

updateModeButtons();
setStatus("Ready - RAG selected");
