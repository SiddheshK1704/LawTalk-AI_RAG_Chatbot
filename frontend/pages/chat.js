import { sendMessageToAPI } from '../services/api.js';
import { saveChatMessage, getChatHistory, getCurrentUser } from '../services/supabase.js';
import { createUserBubble, createBotBubble, createLoadingBubble } from '../components/chatBubble.js';

let chatContainer;

export async function initChat() {
    const chatHTML = `
        <div id="chatOverlay" class="fixed inset-0 z-[200] bg-black/90 backdrop-blur-xl flex flex-col">
            <div class="flex justify-between items-center px-6 py-4 border-b border-white/10 glass rounded-none">
                <div class="flex items-center gap-3">
                    <i class="fas fa-balance-scale text-blue-400 text-2xl"></i>
                    <h2 class="text-xl font-bold">LawTalk Assistant</h2>
                </div>
                <button id="closeChatBtn" class="text-gray-300 hover:text-white text-2xl px-3">&times;</button>
            </div>
            <div id="chatMessagesContainer" class="flex-1 overflow-y-auto p-5 space-y-4 scroll-smooth"></div>
            <div class="p-5 border-t border-white/10 bg-black/30">
                <div class="flex gap-3 max-w-4xl mx-auto">
                    <input type="text" id="chatInput" placeholder="Ask a legal question..." class="flex-1 bg-black/40 border border-white/20 rounded-2xl px-5 py-3 text-white outline-none focus:border-blue-500 transition">
                    <button id="sendMsgBtn" class="bg-blue-600 hover:bg-blue-500 rounded-2xl px-6 py-3 transition-all btn-glow"><i class="fas fa-paper-plane"></i></button>
                </div>
                <p class="text-gray-500 text-xs text-center mt-3">AI-generated responses for informational purposes only. Not legal advice.</p>
            </div>
        </div>
    `;
    
    document.getElementById('app').innerHTML = chatHTML;
    chatContainer = document.getElementById('chatMessagesContainer');
    
    await loadChatHistory();
    
    document.getElementById('closeChatBtn')?.addEventListener('click', () => {
        location.reload();
    });
    
    document.getElementById('sendMsgBtn')?.addEventListener('click', sendMessage);
    document.getElementById('chatInput')?.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendMessage();
    });
}

async function loadChatHistory() {
    const user = getCurrentUser();
    if (!user) return;
    
    const history = await getChatHistory(user.id);
    chatContainer.innerHTML = '';
    
    if (history.length === 0) {
        chatContainer.appendChild(createBotBubble('👋 Hello! I\'m LawTalk AI. Ask me any legal question, from contract review to intellectual property. How can I help?'));
    } else {
        history.forEach(msg => {
            chatContainer.appendChild(createUserBubble(msg.query));
            chatContainer.appendChild(createBotBubble(msg.response));
        });
    }
    scrollToBottom();
}

async function sendMessage() {
    const input = document.getElementById('chatInput');
    const message = input.value.trim();
    if (!message) return;
    
    // Add user message
    chatContainer.appendChild(createUserBubble(message));
    input.value = '';
    scrollToBottom();
    
    // Add loading indicator
    const loadingBubble = createLoadingBubble();
    chatContainer.appendChild(loadingBubble);
    scrollToBottom();
    
    try {
        const response = await sendMessageToAPI(message);
        loadingBubble.remove();
        chatContainer.appendChild(createBotBubble(response));
        
        // Save to Supabase
        const user = getCurrentUser();
        if (user) {
            await saveChatMessage(user.id, message, response);
        }
    } catch (error) {
        loadingBubble.remove();
        chatContainer.appendChild(createBotBubble('Sorry, I encountered an error. Please try again.'));
        console.error('Chat error:', error);
    }
    scrollToBottom();
}

function scrollToBottom() {
    chatContainer.scrollTop = chatContainer.scrollHeight;
}