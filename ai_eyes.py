#!/usr/bin/env python3
"""
CriadorDeShopifys - Vision Agent
Controle de tela via OCR+OpenCV para automação
"""

import cv2
import numpy as np
import pytesseract
from PIL import Image
import pyautogui
import sys
import time
import json

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05

def shot():
    """Screenshot como numpy array"""
    return cv2.cvtColor(np.array(pyautogui.screenshot()), cv2.COLOR_RGB2BGR)

def scan(compact=True):
    """Escaneia tela. compact=True retorna formato menor"""
    img = shot()
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    d = pytesseract.image_to_data(rgb, lang='por+eng', output_type=pytesseract.Output.DICT)
    
    els = []
    for i in range(len(d['text'])):
        t = d['text'][i].strip()
        if int(d['conf'][i]) > 40 and t and len(t) > 1:
            x, y, w, h = d['left'][i], d['top'][i], d['width'][i], d['height'][i]
            els.append({'t': t, 'x': x+w//2, 'y': y+h//2})
    
    if compact:
        # Formato ultra compacto: "texto@x,y"
        return '\n'.join([f"{e['t']}@{e['x']},{e['y']}" for e in els])
    return els

def click(x, y):
    """Clica na posição"""
    pyautogui.click(int(x), int(y))
    return f"ok@{x},{y}"

def clickt(text):
    """Clica no primeiro texto encontrado"""
    els = scan(compact=False)
    text_lower = text.lower()
    for e in els:
        if text_lower in e['t'].lower():
            pyautogui.click(e['x'], e['y'])
            return f"ok:{e['t']}@{e['x']},{e['y']}"
    return f"404:{text}"

def write(text):
    """Digita texto"""
    for char in text:
        pyautogui.write(char) if char.isascii() else pyautogui.press('space')
    return f"ok:{len(text)}"

def key(k):
    """Pressiona tecla"""
    pyautogui.press(k)
    return f"ok:{k}"

def hot(*keys):
    """Hotkey combo"""
    pyautogui.hotkey(*keys)
    return f"ok:{'+'.join(keys)}"

def wait(ms=500):
    """Espera ms milissegundos"""
    time.sleep(ms/1000)
    return f"ok:{ms}ms"

def mouse(x, y):
    """Move mouse"""
    pyautogui.moveTo(int(x), int(y))
    return f"ok@{x},{y}"

def scroll(n):
    """Scroll (+ cima, - baixo)"""
    pyautogui.scroll(int(n))
    return f"ok:{n}"

# CLI
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("scan|click X Y|clickt TXT|write TXT|key K|hot K1 K2|wait MS|mouse X Y|scroll N")
        sys.exit(0)
    
    cmd = sys.argv[1]
    args = sys.argv[2:]
    
    if cmd == "scan": print(scan())
    elif cmd == "click" and len(args) >= 2: print(click(args[0], args[1]))
    elif cmd == "clickt": print(clickt(' '.join(args)))
    elif cmd == "write": print(write(' '.join(args)))
    elif cmd == "key": print(key(args[0]))
    elif cmd == "hot": print(hot(*args))
    elif cmd == "wait": print(wait(int(args[0]) if args else 500))
    elif cmd == "mouse" and len(args) >= 2: print(mouse(args[0], args[1]))
    elif cmd == "scroll": print(scroll(args[0]))
    else: print(f"?:{cmd}")
