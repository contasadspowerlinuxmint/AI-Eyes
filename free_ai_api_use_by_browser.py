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
        # Usando perfil padrão para tentar pegar o login existente
        # Ajuste o caminho se necessário: ~/.config/google-chrome
        user_data_dir = os.path.expanduser("~/.config/google-chrome-api-free")
        self.browser = await zd.start(
            user_data_dir=user_data_dir,
            headless=False # Mantemos visível para o Bruno ver o que está acontecendo
        )
        self.page = await self.browser.get(GEMINI_URL)
        await asyncio.sleep(5)
        print("Browser pronto.")

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
            if not self.page:
                await self.start()
            
            await self.ensure_pro_mode()

            # Localiza a caixa de texto
            # O seletar do Gemini costuma ser um div contenteditable ou textarea
            textarea = await self.page.query_selector('div[role="textbox"]') or \
                       await self.page.query_selector('textarea')
            
            if not textarea:
                raise Exception("Caixa de texto não encontrada")

            # Limpa e digita
            await textarea.click()
            await textarea.type(prompt)
            await asyncio.sleep(1)
            
            # Clica em enviar
            send_button = await self.page.query_selector('button[aria-label="Enviar comando"]') or \
                          await self.page.query_selector('button:has(mat-icon:text("send"))')
            
            if send_button:
                await send_button.click()
            else:
                # Fallback: Enter
                await self.page.keyboard.press("Enter")

            # Espera a resposta começar e terminar
            # O Gemini mostra "O Gemini está digitando..." ou similar
            print("Aguardando resposta...")
            await asyncio.sleep(5) # Espera inicial
            
            # Tenta pegar o último bloco de conteúdo
            last_response = ""
            for _ in range(30): # Timeout de 60 segundos
                responses = await self.page.query_selector_all('message-content')
                if responses:
                    current_text = await responses[-1].get_text()
                    if current_text and current_text == last_response and len(current_text) > 0:
                        # Se o texto parou de mudar, assumimos que terminou
                        return current_text
                    last_response = current_text
                await asyncio.sleep(2)
            
            return last_response

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
