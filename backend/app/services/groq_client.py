from groq import Groq
import os

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def get_llm_response(prompt: str):
    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[{"role": "user", "content": prompt}]
    )

    return response.choices[0].message.content