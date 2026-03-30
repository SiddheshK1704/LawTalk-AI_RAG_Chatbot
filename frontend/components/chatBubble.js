export function createUserBubble(message) {
    const bubble = document.createElement('div');
    bubble.className = 'chat-bubble-user p-4 max-w-[85%] md:max-w-[70%] text-white ml-auto text-right';
    bubble.innerHTML = `<div>${escapeHtml(message)}</div>`;
    return bubble;
}

export function createBotBubble(message) {
    const bubble = document.createElement('div');
    bubble.className = 'chat-bubble-bot p-4 max-w-[85%] md:max-w-[70%] text-white';
    bubble.innerHTML = `<div><i class="fas fa-gavel text-blue-300 mr-2"></i>${escapeHtml(message)}</div>`;
    return bubble;
}

export function createLoadingBubble() {
    const bubble = document.createElement('div');
    bubble.className = 'chat-bubble-bot p-4 max-w-[85%] text-white';
    bubble.innerHTML = '<i class="fas fa-circle-notch fa-spin"></i> Thinking...';
    return bubble;
}

function escapeHtml(str) {
    return str.replace(/[&<>]/g, function(m) {
        if (m === '&') return '&amp;';
        if (m === '<') return '&lt;';
        if (m === '>') return '&gt;';
        return m;
    });
}