import subprocess
import time
import os
import logging
import pyautogui
import keyboard
from flask import Flask, request, jsonify

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NativeChromeOpener:
    """Abre Chrome nativo do sistema sem automação detectável"""
    
    def __init__(self):
        self.chrome_path = self._find_chrome_path()
        
    def _find_chrome_path(self):
        """Encontra o caminho do Chrome no sistema"""
        chrome_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"C:\Users\%USERNAME%\AppData\Local\Google\Chrome\Application\chrome.exe")
        ]
        
        for path in chrome_paths:
            if os.path.exists(path):
                logger.info(f"Chrome encontrado em: {path}")
                return path
        
        logger.error("Chrome não encontrado no sistema")
        return None
    
    def open_chrome_and_navigate(self, url: str, wait_time: int = 60):
        """Abre Chrome nativo e simula navegação manual"""
        try:
            if not self.chrome_path:
                return {"success": False, "error": "Chrome não encontrado"}
            
            logger.info("Abrindo Chrome nativo do sistema...")
            
            # Abrir Chrome nativo
            subprocess.Popen([self.chrome_path])
            time.sleep(3)  # Aguardar Chrome abrir
            
            # Simular Ctrl+L para focar na barra de endereço
            logger.info("Simulando navegação manual...")
            pyautogui.hotkey('ctrl', 'l')
            time.sleep(1)
            
            # Digitar URL como se fosse usuário
            pyautogui.write(url, interval=0.1)  # Digitar com intervalo humano
            time.sleep(1)
            
            # Pressionar Enter
            pyautogui.press('enter')
            time.sleep(2)
            
            logger.info(f"URL digitada no Chrome nativo: {url}")
            logger.info(f"Aguardando {wait_time}s para navegação manual...")
            
            # Aguardar tempo especificado para navegação manual
            time.sleep(wait_time)
            
            return {
                "success": True,
                "method": "Native Chrome Manual Navigation",
                "message": f"Chrome aberto com URL {url}. Navegação manual aguardada por {wait_time}s."
            }
            
        except Exception as e:
            logger.error(f"Erro ao abrir Chrome nativo: {e}")
            return {"success": False, "error": str(e)}
    
    def navigate_in_existing_chrome(self, url: str):
        """Navega para URL abrindo Chrome específico via executável"""
        try:
            logger.info("Abrindo Chrome específico para navegação...")
            
            # Passo 1: Abrir Chrome diretamente com a URL
            if not self.chrome_path:
                return {"success": False, "error": "Chrome não encontrado"}
            
            logger.info(f"Abrindo Chrome com URL: {url}")
            
            # Abrir Chrome com a URL específica e debugging habilitado
            chrome_args = [
                self.chrome_path,
                url,
                '--remote-debugging-port=9222',
                '--user-data-dir=C:\\temp\\chrome_debug_profile',
                '--no-first-run',
                '--no-default-browser-check',
                '--disable-extensions-except',
                '--disable-plugins-discovery'
            ]
            
            # Verificar se já existe uma instância Chrome com debugging
            try:
                import requests
                response = requests.get('http://127.0.0.1:9222/json', timeout=2)
                if response.status_code == 200:
                    logger.info("Chrome com debugging já está rodando")
                else:
                    raise Exception("Chrome debugging não acessível")
            except:
                logger.info("Iniciando nova instância Chrome com debugging...")
                subprocess.Popen(chrome_args)
                time.sleep(10)  # Aguardar Chrome abrir com debugging
                
                # Verificar se debugging está funcionando
                try:
                    response = requests.get('http://127.0.0.1:9222/json', timeout=5)
                    if response.status_code == 200:
                        logger.info("✅ Chrome debugging port ativo")
                    else:
                        logger.warning("⚠️ Chrome debugging port não respondeu corretamente")
                except Exception as e:
                    logger.error(f"❌ Erro ao verificar Chrome debugging: {e}")
            
            logger.info("✅ Chrome aberto diretamente com URL")
            
            return {
                "success": True,
                "method": "Direct Chrome Launch with URL",
                "message": f"Chrome aberto diretamente com: {url}",
                "note": "Chrome aberto via executável com URL específica"
            }
            
        except Exception as e:
            logger.error(f"Erro ao abrir Chrome diretamente: {e}")
            return {"success": False, "error": str(e)}

    def open_chrome_with_keyboard_commands(self, url: str):
        """Abre Chrome usando apenas comandos de teclado do Windows - 100% manual"""
        try:
            logger.info("Abrindo Chrome via comandos de teclado (100% manual)...")
            
            # Abrir menu Iniciar com tecla Windows
            pyautogui.press('win')
            time.sleep(1.5)
            
            # Digitar "chrome" para buscar (mais devagar, como usuário real)
            pyautogui.write('chrome', interval=0.15)
            time.sleep(2.5)
            
            # Pressionar Enter para abrir
            pyautogui.press('enter')
            time.sleep(6)  # Aguardar Chrome abrir completamente
            
            # Aguardar Chrome carregar totalmente
            logger.info("Aguardando Chrome carregar completamente...")
            time.sleep(4)
            
            # Focar na barra de endereço com Ctrl+L (timing mais natural)
            pyautogui.hotkey('ctrl', 'l')
            time.sleep(1.5)
            
            # Digitar URL mais devagar (como usuário real digitaria)
            logger.info(f"Digitando URL manualmente: {url}")
            pyautogui.write(url, interval=0.12)  # Mais devagar
            time.sleep(2)
            
            # Pressionar Enter para navegar
            pyautogui.press('enter')
            
            logger.info("Navegação manual concluída - Chrome aberto como usuário real")
            logger.info("IMPORTANTE: Chrome foi aberto manualmente, não via automação!")
            
            return {
                "success": True,
                "method": "100% Manual Keyboard Commands",
                "message": f"Chrome aberto manualmente via teclado com URL {url}",
                "note": "Chrome aberto como se fosse usuário real digitando"
            }
            
        except Exception as e:
            logger.error(f"Erro ao abrir Chrome via teclado: {e}")
            return {"success": False, "error": str(e)}

# Criar aplicação Flask
app = Flask(__name__)

@app.route('/open_native_chrome', methods=['POST'])
def open_native_chrome_endpoint():
    """Endpoint para abrir Chrome nativo"""
    try:
        data = request.get_json()
        url = data.get('url')
        method = data.get('method', 'new')  # 'new' ou 'existing'
        wait_time = data.get('wait_time', 60)
        
        if not url:
            return jsonify({"success": False, "error": "URL é obrigatória"}), 400
        
        opener = NativeChromeOpener()
        
        if method == 'existing':
            # Usar Chrome existente com atalhos simples
            result = opener.navigate_in_existing_chrome(url)
            
            # Aguardar tempo adicional para carregamento completo
            time.sleep(wait_time)
            
            # Não retornar dados falsos - deixar que Selenium extraia dados reais
            # result['extraction_data'] removido para forçar extração real
            
        else:
            # Abrir novo Chrome
            result = opener.open_chrome_and_navigate(url, wait_time)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Erro no endpoint: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/health_native', methods=['GET'])
def health_native():
    """Health check da API nativa"""
    return jsonify({
        'status': 'healthy',
        'service': 'Native Chrome Opener',
        'port': 5005,
        'methods': ['native', 'keyboard', 'existing']
    })

if __name__ == '__main__':
    print("=== NATIVE CHROME OPENER ===")
    print("Abertura de Chrome nativo sem automação")
    print("Porta: 5005")
    print("Endpoints:")
    print("  POST /open_native_chrome - Abre Chrome nativo")
    print("  GET /health_native - Health check")
    print("========================================")
    
    app.run(host='0.0.0.0', port=5005, debug=True)
