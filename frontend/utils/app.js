async function ask() {
    const query = document.getElementById("query").value;

    const res = await fetch("http://127.0.0.1:8000/ask", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({ query })
    });

    const data = await res.json();

    document.getElementById("response").innerText =
        `[${data.mode}] ${data.answer}`;
}