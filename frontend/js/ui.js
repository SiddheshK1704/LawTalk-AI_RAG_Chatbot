window.onload = () => {
  const input = document.getElementById("input");
  const sendBtn = document.getElementById("sendBtn");
  const messages = document.getElementById("messages");

  if (!input || !sendBtn || !messages) {
    console.error("Elements not found");
    return;
  }

  sendBtn.onclick = async () => {
    const text = input.value;

    addMessage(text, "user");

    const res = await fetch("http://127.0.0.1:8000/ask", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ query: text })
    });

    const data = await res.json();

    addMessage(data.answer, "bot");

    input.value = "";
  };

  function addMessage(text, type) {
    const div = document.createElement("div");

    div.className =
      "p-3 rounded-xl max-w-[70%] " +
      (type === "user"
        ? "bg-blue-600 ml-auto"
        : "bg-white/20");

    div.innerText = text;

    messages.appendChild(div);
  }
};