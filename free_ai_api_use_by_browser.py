import asyncio
import zendriver as zd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import uvicorn
import os

app = FastAPI(title="Free AI API via Browser")

# Configurações do Gemini
GEMINI_URL = "https://gemini.google.com/app"

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

    async def start(self):
        print("Iniciando browser...")
        # Usando um diretório de perfil persistente
        user_data_dir = os.path.expanduser("~/Desktop/gemini_profile")
        if not os.path.exists(user_data_dir):
            os.makedirs(user_data_dir)
            
        self.browser = await zd.start(
            user_data_dir=user_data_dir,
            headless=False
        )
        self.page = await self.browser.get(GEMINI_URL)
        print("Browser aberto. Verifique se o login é necessário no monitor.")
        await asyncio.sleep(5)

    async def ensure_pro_mode(self):
        """Garante que o modo Pro está selecionado"""
        try:
            # Tenta encontrar o seletor de modo (Pro/Flash)
            # O seletor geralmente tem o texto "Pro" ou "Flash"
            selector = await self.page.query_selector('button[aria-haspopup="true"]')
            if selector:
                text = await selector.get_text()
                if "Pro" not in text:
                    await selector.click()
                    await asyncio.sleep(1)
                    pro_option = await self.page.query_selector('text="Gemini Advanced"') or \
                                 await self.page.query_selector('text="Pro"')
                    if pro_option:
                        await pro_option.click()
                        await asyncio.sleep(2)
        except Exception as e:
            print(f"Erro ao verificar modo Pro: {e}")

    async def chat(self, prompt: str) -> str:
        async with self.lock:
            try:
                if not self.browser:
                    await self.start()
                
                print(f"Processando prompt: {prompt[:50]}...")
                
                # Garante que estamos na página do Gemini
                if "gemini.google.com" not in self.page.url:
                    print("Navegando para o Gemini...")
                    await self.page.get(GEMINI_URL)
                    await asyncio.sleep(5)

                # Localiza a caixa de texto
                # Seletores comuns: 'div[role="textbox"]', 'textarea', '.input-area'
                textarea = await self.page.select('div[role="textbox"]', timeout=10)
                
                if not textarea:
                    print("Tentando seletor alternativo...")
                    textarea = await self.page.select('textarea', timeout=5)
                
                if not textarea:
                    raise Exception("Não encontrei a caixa de texto do Gemini. O site carregou?")

                # Digita o prompt
                print("Digitando...")
                await textarea.send_keys(prompt)
                await asyncio.sleep(1)
                
                # Clica no botão de enviar
                print("Tentando enviar...")
                try:
                    # Tenta encontrar o botão por vários seletores comuns
                    send_button = await self.page.select('button[aria-label*="Enviar"]', timeout=3) or \
                                  await self.page.select('button.send-button', timeout=1)
                    if send_button:
                        print("Clicando no botão enviar...")
                        await send_button.click()
                    else:
                        print("Botão não encontrado pelo seletor, tentando Enter...")
                        await textarea.send_keys('\n')
                except Exception:
                    print("Erro ao localizar botão, tentando Enter...")
                    await textarea.send_keys('\n')
                
                print("Aguardando resposta...")
                await asyncio.sleep(8) 
                
                last_text = ""
                for i in range(20): # 60 segundos total
                    elements = await self.page.select_all('message-content')
                    if elements:
                        # Pega o texto do último elemento de resposta
                        current_text = elements[-1].text
                        if current_text:
                            if current_text == last_text and len(current_text) > 2:
                                print("Resposta completa.")
                                return current_text
                            last_text = current_text
                    await asyncio.sleep(3)
                
                return last_text or "O Gemini não respondeu a tempo."
            except Exception as e:
                import traceback
                error_msg = f"Erro no BrowserAI: {str(e)}\n{traceback.format_exc()}"
                print(error_msg)
                raise Exception(error_msg)

ai_browser = BrowserAI()

@app.on_event("startup")
async def startup_event():
    # Não iniciamos aqui para não travar o boot da API se o browser falhar
    pass

@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    # Pega apenas a última mensagem do usuário para simplificar o "mesmo chat"
    user_prompt = request.messages[-1].content
    
    try:
        response_text = await ai_browser.chat(user_prompt)
        return {
            "id": "chatcmpl-free",
            "object": "chat.completion",
            "created": 123456789,
            "model": request.model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": response_text,
                    },
                    "finish_reason": "stop"
                }
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
