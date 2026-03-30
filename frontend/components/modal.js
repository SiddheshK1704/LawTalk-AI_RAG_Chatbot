import { handleAuth } from '../utils/auth.js';

export function initModal() {
    const modalHTML = `
        <div id="authModal" class="fixed inset-0 z-[100] flex items-center justify-center backdrop-blur-md bg-black/50 transition-all duration-300 opacity-0 pointer-events-none">
            <div class="glass-card w-[90%] max-w-md p-6 md:p-8 rounded-2xl shadow-2xl transform transition-all duration-300 scale-95">
                <div class="flex justify-between items-center mb-5">
                    <h2 class="text-2xl font-bold text-white">Access LawTalk</h2>
                    <button id="closeModalBtn" class="text-gray-400 hover:text-white text-2xl">&times;</button>
                </div>
                <div class="space-y-4">
                    <div>
                        <label class="block text-sm font-medium text-gray-300 mb-1">Email address</label>
                        <input type="email" id="authEmail" class="w-full bg-black/30 border border-white/20 rounded-xl px-4 py-3 text-white outline-none focus:border-blue-500 transition" placeholder="you@example.com">
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-300 mb-1">Password</label>
                        <input type="password" id="authPassword" class="w-full bg-black/30 border border-white/20 rounded-xl px-4 py-3 text-white outline-none focus:border-blue-500 transition" placeholder="••••••••">
                    </div>
                    <button id="submitAuthBtn" class="w-full bg-blue-600 hover:bg-blue-500 text-white font-semibold py-3 rounded-xl transition-all btn-glow mt-2">Sign up / Log in</button>
                    <p class="text-xs text-center text-gray-400 mt-3">By continuing, you agree to AI Legal Terms</p>
                </div>
            </div>
        </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', modalHTML);
    
    // Modal controls
    window.showAuthModal = () => {
        const modal = document.getElementById('authModal');
        modal.classList.remove('opacity-0', 'pointer-events-none');
        modal.classList.add('opacity-100', 'pointer-events-auto');
        gsap.fromTo(modal.querySelector('.glass-card'), 
            { scale: 0.9, opacity: 0 }, 
            { scale: 1, opacity: 1, duration: 0.3, ease: "backOut" }
        );
    };
    
    window.hideAuthModal = () => {
        const modal = document.getElementById('authModal');
        modal.classList.add('opacity-0', 'pointer-events-none');
        modal.classList.remove('opacity-100', 'pointer-events-auto');
    };
    
    document.getElementById('closeModalBtn')?.addEventListener('click', () => window.hideAuthModal());
    document.getElementById('submitAuthBtn')?.addEventListener('click', async () => {
        const email = document.getElementById('authEmail').value;
        const password = document.getElementById('authPassword').value;
        const success = await handleAuth(email, password);
        if (success) {
            window.hideAuthModal();
            document.getElementById('authEmail').value = '';
            document.getElementById('authPassword').value = '';
            if (window.openChatFromLanding) window.openChatFromLanding();
        } else {
            alert("Authentication failed. Please check your credentials.");
        }
    });
}