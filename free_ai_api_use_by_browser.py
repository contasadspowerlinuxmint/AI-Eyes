import asyncio
import zendriver as zd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import uvicorn
import os
import time
import traceback

app = FastAPI(title="Free AI API via Browser")

# Configurações
GEMINI_URL = "https://gemini.google.com/app"
USER_EMAIL = "contasadspowerlinuxmint@gmail.com"
USER_PASS = "farm2026"
IDLE_TIMEOUT = 300  # 5 minutos em segundos

class Message(BaseModel):
    role: str
    content: str

class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[Message]
    stream: Optional[bool] = False

class BrowserAI:
    def __init__(self):
        self.browser = None
        self.page = None
        self.lock = asyncio.Lock()
        self.last_activity = 0
        self.monitor_task = None

    async def start(self):
        print("Iniciando browser (Headless)...")
        user_data_dir = os.path.expanduser("~/Desktop/gemini_profile")
        if not os.path.exists(user_data_dir):
            os.makedirs(user_data_dir)
            
        self.browser = await zd.start(
            user_data_dir=user_data_dir,
            headless=True  # Agora em modo headless
        )
        self.page = await self.browser.get(GEMINI_URL)
        await asyncio.sleep(5)
        
        # Verifica se precisa logar
        if "accounts.google.com" in self.page.url:
            print("Login necessário. Iniciando automação de login...")
            await self.login()
        
        self.last_activity = time.time()
        if not self.monitor_task:
            self.monitor_task = asyncio.create_task(self.idle_monitor())
        
        print("Browser pronto.")

    async def login(self):
        try:
            # Email
            email_field = await self.page.select('input[type="email"]')
            if email_field:
                await email_field.send_keys(USER_EMAIL)
                await self.page.key_press("Enter")
                await asyncio.sleep(5)
            
            # Senha
            pass_field = await self.page.select('input[type="password"]')
            if pass_field:
                await pass_field.send_keys(USER_PASS)
                await self.page.key_press("Enter")
                await asyncio.sleep(8)
            
            # Verifica se voltou para o Gemini
            if "gemini.google.com" not in self.page.url:
                await self.page.get(GEMINI_URL)
                await asyncio.sleep(5)
        except Exception as e:
            print(f"Erro no login: {e}")

    async def idle_monitor(self):
        """Fecha o browser após 5 minutos de inatividade"""
        while True:
            await asyncio.sleep(30)
            if self.browser and (time.time() - self.last_activity > IDLE_TIMEOUT):
                print("Inatividade detectada. Fechando browser...")
                async with self.lock:
                    try:
                        await self.browser.stop()
                    except:
                        pass
                    self.browser = None
                    self.page = None

    async def chat(self, prompt: str) -> str:
        async with self.lock:
            self.last_activity = time.time()
            try:
                if not self.browser:
                    await self.start()
                
                print(f"Processando prompt: {prompt[:50]}...")
                
                if "gemini.google.com" not in self.page.url:
                    await self.page.get(GEMINI_URL)
                    await asyncio.sleep(5)

                textarea = await self.page.select('div[role="textbox"]', timeout=15)
                if not textarea:
                    textarea = await self.page.select('textarea', timeout=5)
                
                if not textarea:
                    raise Exception("Caixa de texto não encontrada.")

                await textarea.send_keys(prompt)
                await asyncio.sleep(1)
                
                # Tenta enviar
                try:
                    send_button = await self.page.select('button[aria-label*="Enviar"]', timeout=3)
                    if send_button:
                        await send_button.click()
                    else:
                        await textarea.send_keys('\n')
                except:
                    await textarea.send_keys('\n')
                
                print("Aguardando resposta...")
                await asyncio.sleep(8) 
                
                last_text = ""
                for _ in range(30):
                    elements = await self.page.select_all('message-content')
                    if elements:
                        current_text = elements[-1].text
                        if current_text:
                            if current_text == last_text and len(current_text) > 2:
                                self.last_activity = time.time()
                                return current_text
                            last_text = current_text
                    await asyncio.sleep(3)
                
                self.last_activity = time.time()
                return last_text
            except Exception as e:
                print(f"Erro: {e}")
                raise e

ai_browser = BrowserAI()

@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    user_prompt = request.messages[-1].content
    try:
        response_text = await ai_browser.chat(user_prompt)
        return {
            "id": "chatcmpl-free",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": request.model,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": response_text}, "finish_reason": "stop"}]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
