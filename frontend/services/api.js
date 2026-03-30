const API_BASE_URL = 'https://your-fastapi-backend.com'; // Replace with your actual backend URL

export async function sendMessageToAPI(query) {
    // For demo/development without backend
    const useMock = API_BASE_URL === 'https://your-fastapi-backend.com';
    
    if (useMock) {
        await new Promise(resolve => setTimeout(resolve, 800));
        
        const lowerQuery = query.toLowerCase();
        if (lowerQuery.includes('contract')) {
            return "Under common law, a valid contract requires offer, acceptance, consideration, and mutual intent. Need specific clause review?";
        } else if (lowerQuery.includes('copyright')) {
            return "Copyright protects original works of authorship. Duration: life of author + 70 years. Fair use is a key defense.";
        } else if (lowerQuery.includes('trademark')) {
            return "Trademarks protect brand identifiers like names, logos, and slogans. Registration provides nationwide protection and legal presumptions.";
        } else {
            return "I'm an AI legal assistant. Based on general principles, you should seek formal counsel for binding legal advice. Would you like me to clarify any specific area of law?";
        }
    }
    
    // Real API call
    try {
        const response = await fetch(`${API_BASE_URL}/ask`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query })
        });
        
        const data = await response.json();
        return data.response || data.answer || "I've analyzed your query. Please consult a licensed attorney for binding advice.";
    } catch (error) {
        console.error('API Error:', error);
        throw new Error('Failed to get response from AI service');
    }
}