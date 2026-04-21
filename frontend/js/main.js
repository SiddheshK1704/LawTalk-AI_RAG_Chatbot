const app = document.getElementById("app");

const modeLabels = {
  rag: "RAG",
  groq: "Groq",
};

function escapeHtml(text) {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function navbar({ compact = false } = {}) {
  return `
    <header class="sticky top-0 z-30 border-b border-white/10 bg-ink/80 backdrop-blur-xl">
      <div class="mx-auto flex max-w-7xl items-center justify-between px-5 py-4 sm:px-8">
        <a href="/" class="flex items-center gap-3">
          <span class="grid h-11 w-11 place-items-center rounded-2xl border border-gold/40 bg-gold/10 text-lg font-bold text-gold">L</span>
          <div>
            <p class="font-display text-lg tracking-tight text-paper">LawTalk</p>
            <p class="text-xs uppercase tracking-[0.35em] text-paper/50">Indian Legal AI</p>
          </div>
        </a>
        <nav class="hidden items-center gap-8 text-sm text-paper/70 md:flex">
          <a href="/#features" class="transition hover:text-paper">Features</a>
          <a href="/#workflow" class="transition hover:text-paper">Workflow</a>
          <a href="/#faq" class="transition hover:text-paper">FAQ</a>
        </nav>
        <div class="flex items-center gap-3">
          ${compact ? '<a href="/" class="ghost-button">Back Home</a>' : ""}
          <a href="/chat" class="primary-button">${compact ? "Open Chat" : "Try The Assistant"}</a>
        </div>
      </div>
    </header>
  `;
}

function landingPage() {
  app.innerHTML = `
    <div class="relative overflow-hidden">
      <div class="pointer-events-none absolute inset-0 hero-mesh opacity-80"></div>
      ${navbar()}
      <main>
        <section class="relative mx-auto grid min-h-[calc(100vh-88px)] max-w-7xl items-center gap-16 px-5 py-14 sm:px-8 lg:grid-cols-[1.15fr_0.85fr] lg:py-20">
          <div class="space-y-8 reveal" data-delay="0">
            <div class="inline-flex items-center gap-3 rounded-full border border-white/10 bg-white/5 px-4 py-2 text-xs uppercase tracking-[0.32em] text-paper/70">
              <span class="h-2 w-2 rounded-full bg-mint shadow-[0_0_18px_rgba(106,227,185,0.9)]"></span>
              FastAPI-Powered Legal Research Companion
            </div>
            <div class="space-y-5">
              <h1 class="max-w-4xl font-display text-5xl leading-[0.95] tracking-tight text-paper sm:text-6xl lg:text-7xl">
                Legal answers grounded in your documents, not generic chatbot noise.
              </h1>
              <p class="max-w-2xl text-lg leading-8 text-paper/70 sm:text-xl">
                LawTalk combines a focused landing experience with a dedicated chat workspace backed by your FastAPI RAG service, so users can move from trust to action without leaving the app.
              </p>
            </div>
            <div class="flex flex-col gap-4 sm:flex-row">
              <a href="/chat" class="primary-button justify-center text-base">Start Chatting</a>
              <a href="#features" class="ghost-button justify-center text-base">See How It Works</a>
            </div>
            <div class="grid gap-4 sm:grid-cols-3">
              <div class="stat-card reveal" data-delay="100">
                <p class="stat-value">RAG</p>
                <p class="stat-label">Answers constrained to your legal context</p>
              </div>
              <div class="stat-card reveal" data-delay="200">
                <p class="stat-value">FastAPI</p>
                <p class="stat-label">Single backend serving UI and API together</p>
              </div>
              <div class="stat-card reveal" data-delay="300">
                <p class="stat-value">2 Modes</p>
                <p class="stat-label">Switch between retrieval and direct LLM chat</p>
              </div>
            </div>
          </div>

          <div class="relative reveal" data-delay="200">
            <div class="glass-panel overflow-hidden p-6 sm:p-8">
              <div class="mb-6 flex items-center justify-between">
                <div>
                  <p class="text-xs uppercase tracking-[0.35em] text-paper/50">Live Preview</p>
                  <h2 class="mt-2 font-display text-2xl text-paper">Chat Workspace</h2>
                </div>
                <span class="rounded-full border border-mint/40 bg-mint/10 px-3 py-1 text-xs font-semibold text-mint">Online</span>
              </div>
              <div class="space-y-4">
                <div class="chat-card assistant">
                  <p class="chat-label">LawTalk</p>
                  <p>Ask about contracts, compliance, procedures, or rights. Responses can stay tied to your retrieved legal corpus.</p>
                </div>
                <div class="chat-card user">
                  <p class="chat-label">You</p>
                  <p>Summarize the obligations in this employment agreement and highlight risky termination clauses.</p>
                </div>
                <div class="chat-card assistant">
                  <p class="chat-label">LawTalk</p>
                  <p>I can answer using retrieved context or the base model. Open the chat view to continue with your backend.</p>
                </div>
              </div>
              <div class="mt-6 rounded-3xl border border-white/10 bg-white/5 p-4">
                <div class="mb-3 flex items-center gap-3">
                  <span class="h-3 w-3 rounded-full bg-rose-400"></span>
                  <span class="h-3 w-3 rounded-full bg-gold"></span>
                  <span class="h-3 w-3 rounded-full bg-mint"></span>
                </div>
                <div class="space-y-3 text-sm text-paper/60">
                  <div class="flex items-center justify-between rounded-2xl border border-white/10 bg-ink-soft px-4 py-3">
                    <span>Mode</span>
                    <span class="rounded-full bg-white/10 px-3 py-1 text-paper">RAG</span>
                  </div>
                  <div class="flex items-center justify-between rounded-2xl border border-white/10 bg-ink-soft px-4 py-3">
                    <span>Route</span>
                    <span class="font-mono text-xs text-paper/80">POST /ask</span>
                  </div>
                  <div class="flex items-center justify-between rounded-2xl border border-white/10 bg-ink-soft px-4 py-3">
                    <span>Frontend</span>
                    <span class="text-paper/80">HTML + Tailwind + JS</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section id="features" class="mx-auto max-w-7xl px-5 py-16 sm:px-8">
          <div class="mb-10 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
            <div class="reveal" data-delay="0">
              <p class="section-kicker">Features</p>
              <h2 class="section-title">Built to feel like a product, not a demo screen.</h2>
            </div>
            <p class="max-w-2xl text-paper/60 reveal" data-delay="100">
              The landing page handles positioning and trust. The chat page focuses on speed, context visibility, and a clean request path into your FastAPI backend.
            </p>
          </div>
          <div class="grid gap-5 lg:grid-cols-3">
            <article class="feature-card reveal" data-delay="0">
              <p class="feature-index">01</p>
              <h3>Animated first impression</h3>
              <p>Layered gradients, scroll reveals, and subtle motion give the landing page a deliberate visual identity without depending on a frontend framework.</p>
            </article>
            <article class="feature-card reveal" data-delay="120">
              <p class="feature-index">02</p>
              <h3>Single-app delivery</h3>
              <p>FastAPI serves both the UI and the API, which keeps local development and deployment cleaner than maintaining a separate Flask bridge.</p>
            </article>
            <article class="feature-card reveal" data-delay="240">
              <p class="feature-index">03</p>
              <h3>Dedicated legal chat</h3>
              <p>The chat interface supports RAG and direct model modes, request status, auto-scrolling messages, and keyboard submission.</p>
            </article>
          </div>
        </section>

        <section id="workflow" class="mx-auto max-w-7xl px-5 py-16 sm:px-8">
          <div class="grid gap-6 lg:grid-cols-3">
            <div class="workflow-card reveal" data-delay="0">
              <p class="workflow-step">Step 1</p>
              <h3>Open the chat workspace</h3>
              <p>Users land on the product story first, then move into a focused interface built for legal Q&A.</p>
            </div>
            <div class="workflow-card reveal" data-delay="100">
              <p class="workflow-step">Step 2</p>
              <h3>Send a question</h3>
              <p>The frontend posts JSON to your existing `/ask` endpoint, using the same request shape your backend already expects.</p>
            </div>
            <div class="workflow-card reveal" data-delay="200">
              <p class="workflow-step">Step 3</p>
              <h3>Render the answer</h3>
              <p>Responses are shown as message bubbles with mode-aware status text and error handling when the backend is unavailable.</p>
            </div>
          </div>
        </section>

        <section id="faq" class="mx-auto max-w-7xl px-5 py-16 sm:px-8">
          <div class="glass-panel grid gap-8 p-8 lg:grid-cols-[0.9fr_1.1fr]">
            <div class="reveal" data-delay="0">
              <p class="section-kicker">FAQ</p>
              <h2 class="section-title">What changed in the architecture?</h2>
            </div>
            <div class="space-y-5">
              <div class="faq-item reveal" data-delay="100">
                <h3>Does the frontend still need Flask?</h3>
                <p>No. The frontend is now static HTML, Tailwind CSS, and vanilla JavaScript served directly by FastAPI.</p>
              </div>
              <div class="faq-item reveal" data-delay="180">
                <h3>Can the chat still use retrieval?</h3>
                <p>Yes. The interface defaults to <code>rag</code> mode and can switch to <code>groq</code> mode for direct generation.</p>
              </div>
              <div class="faq-item reveal" data-delay="260">
                <h3>Is this ready for local testing?</h3>
                <p>Yes. Once Tailwind is built, running the FastAPI app serves the landing page at <code>/</code> and the chat at <code>/chat</code>.</p>
              </div>
            </div>
          </div>
        </section>
      </main>
    </div>
  `;

  setupRevealAnimations();
}

function chatPage() {
  app.innerHTML = `
    <div class="relative min-h-screen overflow-hidden">
      <div class="pointer-events-none absolute inset-0 hero-mesh opacity-70"></div>
      ${navbar({ compact: true })}
      <main class="relative mx-auto max-w-7xl px-5 py-10 sm:px-8">
        <div class="grid gap-8 lg:grid-cols-[0.34fr_0.66fr]">
          <aside class="space-y-6 reveal" data-delay="0">
            <section class="glass-panel p-6">
              <p class="section-kicker">Connection</p>
              <h1 class="mt-3 font-display text-4xl leading-tight text-paper">Legal chat built on your RAG backend.</h1>
              <p class="mt-4 text-paper/60">
                Ask questions against your retrieved legal context or switch to direct model mode when you need a broader conversational pass.
              </p>
            </section>
            <section class="glass-panel p-6">
              <div class="flex items-center justify-between">
                <div>
                  <p class="text-xs uppercase tracking-[0.32em] text-paper/50">Status</p>
                  <p id="status-text" class="mt-2 text-lg font-semibold text-mint">Ready</p>
                </div>
                <span class="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-paper/60">POST /ask</span>
              </div>
              <div class="mt-6">
                <p class="text-xs uppercase tracking-[0.32em] text-paper/50">Mode</p>
                <div class="mt-3 grid gap-3">
                  <button type="button" class="mode-button is-active" data-mode="rag">
                    <span>RAG</span>
                    <span class="text-xs text-paper/50">Use retrieved legal context</span>
                  </button>
                  <button type="button" class="mode-button" data-mode="groq">
                    <span>Groq</span>
                    <span class="text-xs text-paper/50">Use the base model directly</span>
                  </button>
                </div>
              </div>
            </section>
          </aside>

          <section class="glass-panel flex min-h-[72vh] flex-col overflow-hidden reveal" data-delay="120">
            <div class="border-b border-white/10 px-5 py-5 sm:px-6">
              <p class="text-xs uppercase tracking-[0.32em] text-paper/50">Chat Interface</p>
              <div class="mt-2 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                <h2 class="font-display text-2xl text-paper">LawTalk Assistant</h2>
                <p class="text-sm text-paper/50">Enter sends. Shift + Enter adds a new line.</p>
              </div>
            </div>
            <div id="chat-messages" class="flex-1 space-y-4 overflow-y-auto px-5 py-5 sm:px-6">
              <article class="message-bubble assistant-message">
                <p class="message-label">LawTalk</p>
                <p>Hello. Ask a legal question and I will query your backend.</p>
              </article>
            </div>
            <form id="chat-form" class="border-t border-white/10 px-5 py-5 sm:px-6">
              <label for="message-input" class="sr-only">Your legal question</label>
              <textarea
                id="message-input"
                name="message"
                rows="4"
                class="chat-textarea"
                placeholder="Type your legal question here..."
              ></textarea>
              <div class="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <p class="text-sm text-paper/50">Responses come from your FastAPI route and render in this thread.</p>
                <button id="send-button" type="submit" class="primary-button justify-center">Send Message</button>
              </div>
            </form>
          </section>
        </div>
      </main>
    </div>
  `;

  setupRevealAnimations();
  bindChatInterface();
}

function setupRevealAnimations() {
  const elements = document.querySelectorAll(".reveal");
  if (!elements.length) {
    return;
  }

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) {
          return;
        }
        const delay = entry.target.dataset.delay || 0;
        entry.target.style.transitionDelay = `${delay}ms`;
        entry.target.classList.add("is-visible");
        observer.unobserve(entry.target);
      });
    },
    { threshold: 0.2 }
  );

  elements.forEach((element) => observer.observe(element));
}

function bindChatInterface() {
  const chatForm = document.getElementById("chat-form");
  const messageInput = document.getElementById("message-input");
  const chatMessages = document.getElementById("chat-messages");
  const sendButton = document.getElementById("send-button");
  const statusText = document.getElementById("status-text");
  const modeButtons = document.querySelectorAll(".mode-button");

  let currentMode = "rag";

  function setStatus(text, tone = "ready") {
    statusText.textContent = text;
    statusText.className =
      tone === "error"
        ? "mt-2 text-lg font-semibold text-rose-300"
        : tone === "thinking"
          ? "mt-2 text-lg font-semibold text-gold"
          : "mt-2 text-lg font-semibold text-mint";
  }

  function appendMessage(role, text) {
    const article = document.createElement("article");
    article.className =
      role === "user"
        ? "message-bubble user-message"
        : "message-bubble assistant-message";
    article.innerHTML = `
      <p class="message-label">${role === "user" ? "You" : "LawTalk"}</p>
      <p>${escapeHtml(text).replace(/\n/g, "<br>")}</p>
    `;
    chatMessages.appendChild(article);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  function syncModeButtons() {
    modeButtons.forEach((button) => {
      const isActive = button.dataset.mode === currentMode;
      button.classList.toggle("is-active", isActive);
    });
  }

  async function sendMessage(message) {
    const response = await fetch("/ask", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        query: message,
        mode: currentMode,
      }),
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || data.error || "Unable to get a response.");
    }

    return data;
  }

  chatForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const message = messageInput.value.trim();
    if (!message) {
      setStatus("Enter a legal question first.", "error");
      return;
    }

    appendMessage("user", message);
    messageInput.value = "";
    messageInput.focus();
    sendButton.disabled = true;
    setStatus(`Thinking in ${modeLabels[currentMode]} mode...`, "thinking");

    try {
      const result = await sendMessage(message);
      appendMessage("assistant", result.answer || "No response received.");
      setStatus(`${modeLabels[result.mode || currentMode]} response ready.`);
    } catch (error) {
      appendMessage("assistant", error.message);
      setStatus("Backend request failed.", "error");
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
      syncModeButtons();
      setStatus(`${modeLabels[currentMode]} mode selected.`);
    });
  });

  syncModeButtons();
}

if (window.location.pathname === "/chat" || window.location.pathname.endsWith("/chat.html")) {
  chatPage();
} else {
  landingPage();
}
