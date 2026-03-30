import { getCurrentUser } from '../services/supabase.js';

export function initLanding() {
    const landingHTML = `
        <main id="landingContent" class="relative z-10 pt-28 md:pt-32 pb-16">
            <div class="max-w-7xl mx-auto px-6 md:px-12">
                <div class="flex flex-col lg:flex-row items-center gap-12 lg:gap-20">
                    <div id="heroImage" class="lg:w-1/2 flex justify-center">
                        <div class="relative w-72 md:w-96 floating-img">
                            <div class="absolute inset-0 bg-blue-500/20 blur-3xl rounded-full"></div>
                            <img src="assets/lady.png" alt="Lady Justice" class="relative w-full h-auto drop-shadow-2xl rounded-3xl glass-card p-2">
                        </div>
                    </div>
                    <div id="heroText" class="lg:w-1/2 text-center lg:text-left space-y-6">
                        <h1 class="text-4xl md:text-6xl font-extrabold leading-tight bg-gradient-to-r from-white via-blue-200 to-indigo-300 bg-clip-text text-transparent">AI-Powered Legal Intelligence</h1>
                        <p class="text-gray-300 text-lg md:text-xl max-w-xl mx-auto lg:mx-0">Instant legal insights, contract analysis, and case research — powered by cutting-edge AI. Your 24/7 legal assistant.</p>
                        <div class="flex flex-wrap gap-4 justify-center lg:justify-start pt-4">
                            <button id="heroTryBtn" class="bg-blue-600 hover:bg-blue-500 text-white px-8 py-3 rounded-full text-lg font-semibold transition-all shadow-xl btn-glow flex items-center gap-2"><i class="fas fa-gavel"></i> Try LawTalk</button>
                            <button id="heroAuthBtn" class="glass border border-white/30 hover:bg-white/10 text-white px-8 py-3 rounded-full text-lg font-semibold transition-all btn-glow">Login / Signup</button>
                        </div>
                        <div class="pt-4 text-sm text-blue-300/70 flex items-center gap-2 justify-center lg:justify-start"><i class="fas fa-shield-alt"></i> Free trial • No credit card required</div>
                    </div>
                </div>
            </div>
            <div class="text-center mt-28 opacity-70 animate-pulse">
                <p class="text-sm text-gray-400"><i class="fas fa-chevron-down"></i> Scroll to explore</p>
            </div>
        </main>
        <footer class="relative z-10 border-t border-white/10 mt-24 py-8 px-6 glass rounded-none backdrop-blur-sm">
            <div class="max-w-7xl mx-auto flex flex-col md:flex-row justify-between items-center gap-4">
                <div class="text-gray-400 text-sm">Built with AI • LawTalk — The future of legal assistance</div>
                <a href="#" id="githubLink" class="text-gray-300 hover:text-white transition flex items-center gap-2 text-sm font-medium hover:scale-105 duration-200"><i class="fab fa-github"></i> View on GitHub</a>
            </div>
        </footer>
    `;
    
    document.getElementById('app').innerHTML = landingHTML;
    
    // GSAP Animations
    gsap.from("#navbar", { duration: 0.8, y: -80, opacity: 0, ease: "power3.out" });
    gsap.from("#heroImage", { duration: 1, x: -80, opacity: 0, scale: 0.9, ease: "back.out(0.6)" });
    gsap.from("#heroText", { duration: 1, y: 50, opacity: 0, stagger: 0.2, ease: "power3.out", delay: 0.2 });
    
    // Parallax effect
    ScrollTrigger.create({
        trigger: "body",
        start: "top top",
        end: "bottom bottom",
        onUpdate: (self) => {
            gsap.to(".bg-abstract-glass", { 
                duration: 0.1, 
                backgroundPosition: `0px ${self.progress * 50}px`, 
                ease: "none", 
                overwrite: true 
            });
        }
    });
    
    // Floating hover effect
    const ladyImg = document.querySelector("#heroImage .floating-img");
    if (ladyImg) {
        ladyImg.addEventListener("mouseenter", () => gsap.to(ladyImg, { y: -8, scale: 1.02, duration: 0.4, ease: "power2.out" }));
        ladyImg.addEventListener("mouseleave", () => gsap.to(ladyImg, { y: 0, scale: 1, duration: 0.5 }));
    }
    
    // Event listeners
    document.getElementById('heroTryBtn')?.addEventListener('click', () => {
        if (window.openChatFromLanding) window.openChatFromLanding();
    });
    document.getElementById('heroAuthBtn')?.addEventListener('click', () => {
        if (window.showAuthModal) window.showAuthModal();
    });
    document.getElementById('githubLink')?.addEventListener('click', (e) => {
        e.preventDefault();
        window.open('https://github.com/your-username/lawtalk-ai', '_blank');
    });
}