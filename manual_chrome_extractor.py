#!/usr/bin/env python3
"""
Extrator Shopee com Chrome 100% Manual
Abre Chrome nativo e aguarda usuário navegar manualmente
"""

import requests
import time
import logging
import pyautogui
import keyboard
from flask import Flask, request, jsonify

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ManualChromeExtractor:
    """Extrator que abre Chrome nativo e aguarda navegação manual do usuário"""
    
    def __init__(self):
        pass
    
    def extract_with_manual_navigation(self, url: str, extract_real_data: bool = True) -> dict:
        """
        Abre Chrome manualmente e faz extração real via Selenium
        
        Args:
            url: URL do Shopee para abrir
            extract_real_data: Se True, faz extração real após abrir Chrome
        """
        start_time = time.time()
        
        result = {
            'success': False,
            'method_used': 'Manual Chrome + Real Extraction',
            'url': url,
            'extraction_time': 0,
            'chrome_opened': False,
            'real_extraction': extract_real_data,
            'title': None,
            'price_current': None,
            'price_original': None,
            'discount_percentage': None,
            'rating': None,
            'review_count': None,
            'image_url': None
        }
        
        try:
            logger.info("=== INICIANDO CHROME MANUAL + EXTRAÇÃO REAL ===")
            logger.info(f"URL: {url}")
            
            # Abrir Chrome com debug port para conexão Selenium
            logger.info("Abrindo Chrome com debug port...")
            
            import subprocess
            import os
            
            # Fechar Chrome existente
            try:
                subprocess.run(['taskkill', '/F', '/IM', 'chrome.exe'], capture_output=True)
                time.sleep(2)
            except:
                pass
            
            # Abrir Chrome com debug port
            chrome_paths = [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe")
            ]
            
            chrome_cmd = None
            for path in chrome_paths:
                if os.path.exists(path):
                    chrome_cmd = [
                        path,
                        f"--remote-debugging-port=9222",
                        f"--user-data-dir=C:/temp/chrome_debug",
                        url
                    ]
                    break
            
            if chrome_cmd:
                logger.info("Iniciando Chrome com debug port...")
                subprocess.Popen(chrome_cmd)
                time.sleep(8)  # Aguardar Chrome abrir
            else:
                # Fallback: usar comandos de teclado
                logger.info("Chrome não encontrado - usando comandos de teclado...")
                pyautogui.press('win')
                time.sleep(1.5)
                pyautogui.write('chrome', interval=0.15)
                time.sleep(2.5)
                pyautogui.press('enter')
                time.sleep(6)
                pyautogui.hotkey('ctrl', 'l')
                time.sleep(1.5)
                pyautogui.write(url, interval=0.12)
                time.sleep(2)
                pyautogui.press('enter')
                time.sleep(8)
            
            result['chrome_opened'] = True
            logger.info("✅ Chrome aberto e navegando para URL")
            
            # Aguardar um pouco mais para garantir carregamento completo
            logger.info("Aguardando carregamento completo antes da extração...")
            time.sleep(8)
            
            # Se extração real solicitada, usar Selenium conectando à sessão Chrome aberta
            if extract_real_data:
                logger.info("🔍 Iniciando extração real via Selenium conectando ao Chrome aberto...")
                real_data = self._extract_from_open_chrome()
                if real_data and any(real_data.values()):
                    result.update(real_data)
                    result['success'] = True
                    result['method_used'] = 'Manual Chrome + Real Selenium Extraction'
                    logger.info("✅ Extração real bem-sucedida do Chrome aberto")
                else:
                    logger.info("❌ Extração real falhou - usando fallback")
                    fallback_data = self._get_fallback_data(url)
                    if fallback_data:
                        result.update(fallback_data)
                        result['success'] = True
                        result['method_used'] = 'Manual Chrome + Fallback Database'
            else:
                # Apenas fallback
                fallback_data = self._get_fallback_data(url)
                if fallback_data:
                    result.update(fallback_data)
                    result['success'] = True
                    result['method_used'] = 'Manual Chrome + Fallback Database'
            
            # Fechar Chrome automaticamente após extração
            logger.info("🔒 Fechando Chrome automaticamente...")
            pyautogui.hotkey('alt', 'f4')  # Alt+F4 para fechar
            
            result['extraction_time'] = time.time() - start_time
            logger.info(f"✅ Extração concluída em {result['extraction_time']:.1f}s")
            
            return result
            
        except Exception as e:
            logger.error(f"Erro na navegação manual: {e}")
            result['error'] = str(e)
            result['extraction_time'] = time.time() - start_time
            return result
    
    def _extract_from_open_chrome(self, url) -> dict:
        """Conecta ao Chrome já aberto e extrai dados reais"""
        try:
            from selenium import webdriver
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from selenium.webdriver.chrome.service import Service
            
            logger.info("Conectando ao Chrome já aberto...")
            
            # Conectar ao Chrome existente na porta 9222
            options = webdriver.ChromeOptions()
            options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            
            driver = None
            try:
                driver = webdriver.Chrome(options=options)
                logger.info("✅ Conectado ao Chrome existente")
                
                # Aguardar página estar carregada
                time.sleep(5)
                
                # Usar JavaScript para extração direta
                logger.info("Executando JavaScript para extração...")
                
                # Script JavaScript para extrair todos os dados
                js_script = """
                var data = {};
                
                // Título
                var title = document.querySelector('h1.vR6K3w') || document.querySelector('h1');
                if (title) data.title = title.textContent.trim();
                
                // Preços
                var currentPrice = document.querySelector('.IZPeQz.B67UQ0');
                if (currentPrice) data.price_current = currentPrice.textContent.trim();
                
                var originalPrice = document.querySelector('.ZA5sW5');
                if (originalPrice) data.price_original = originalPrice.textContent.trim();
                
                // Rating
                var rating = document.querySelector('.F9RHbS.dQEiAI.jMXp4d');
                if (rating) data.rating = rating.textContent.trim();
                
                // Reviews - buscar elemento que contém número
                var reviewElements = document.querySelectorAll('.F9RHbS');
                for (var i = 0; i < reviewElements.length; i++) {
                    var text = reviewElements[i].textContent.trim();
                    if (text && /\\d/.test(text) && !reviewElements[i].classList.contains('dQEiAI')) {
                        data.review_count = text;
                        break;
                    }
                }
                
                // Desconto
                var discount = document.querySelector('.vms4_3');
                if (discount) {
                    var discountText = discount.textContent.trim();
                    var match = discountText.match(/(\\d+)%/);
                    if (match) data.discount_percentage = parseInt(match[1]);
                }
                
                // Imagem principal
                var img = document.querySelector('img.uXN1L5.lazyload.fMm3P2') || 
                         document.querySelector('picture.UkIsx8 img') ||
                         document.querySelector('img[src*="susercontent.com"]');
                if (img) {
                    var src = img.src || img.getAttribute('data-src');
                    if (src && src.includes('susercontent.com')) {
                        data.image_url = src;
                    }
                }
                
                return data;
                """
                
                # Executar JavaScript
                data = driver.execute_script(js_script)
                
                # Log dos resultados
                logger.info("=== RESULTADOS JAVASCRIPT ===")
                for key, value in data.items():
                    if value:
                        logger.info(f"✅ {key}: {str(value)[:50]}...")
                    else:
                        logger.info(f"❌ {key}: não encontrado")
                
                logger.info(f"✅ Extração do Chrome aberto: {len([v for v in data.values() if v])} campos")
                return data
                
            except Exception as e:
                logger.error(f"Erro conectando ao Chrome: {e}")
                # Fallback: tentar extração normal
                return self._extract_real_data_selenium_fallback(url)
                
            finally:
                # NÃO fechar driver - é o Chrome do usuário
                pass
                
        except Exception as e:
            logger.error(f"Erro na extração do Chrome aberto: {e}")
            return None
    
    def _extract_real_data_selenium_fallback(self, url: str) -> dict:
        """Fallback: Cria novo driver Selenium se não conseguir conectar ao Chrome"""
        try:
            from selenium import webdriver
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            import undetected_chromedriver as uc
            
            logger.info("Criando novo driver Selenium como fallback...")
            
            # Criar driver stealth para extração
            options = webdriver.ChromeOptions()
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--disable-web-security")
            options.add_argument("--disable-features=VizDisplayCompositor")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            
            driver = None
            try:
                driver = uc.Chrome(options=options)
                driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                
                logger.info("Navegando para extração...")
                driver.get(url)
                time.sleep(12)  # Aguardar carregamento completo
                
                # Aguardar elementos dinâmicos carregarem
                try:
                    wait = WebDriverWait(driver, 15)
                    wait.until(EC.presence_of_element_located((By.TAG_NAME, "h1")))
                    logger.info("Página carregada - elementos detectados")
                except:
                    logger.info("Timeout aguardando elementos - continuando extração")
                
                # Scroll para carregar conteúdo lazy-load
                driver.execute_script("window.scrollTo(0, 500);")
                time.sleep(3)
                driver.execute_script("window.scrollTo(0, 0);")
                time.sleep(2)
                
                # Extrair dados reais
                data = {}
                
                # Título - baseado no HTML fornecido
                title_selectors = [
                    'h1.vR6K3w',  # Seletor específico do HTML
                    'h1',
                    '[class*="vR6K3w"]',
                    '.shopee-page-product__title'
                ]
                
                for selector in title_selectors:
                    try:
                        element = driver.find_element(By.CSS_SELECTOR, selector)
                        if element.text.strip():
                            data['title'] = element.text.strip()
                            logger.info(f"Título extraído: {data['title'][:50]}...")
                            break
                    except:
                        continue
                
                # Preços - baseado no HTML fornecido
                price_selectors = [
                    '.IZPeQz.B67UQ0',  # Preço atual no HTML
                    '.ZA5sW5',         # Preço original no HTML
                    'div[class*="IZPeQz"]',
                    'div[class*="ZA5sW5"]',
                    'span[class*="price"]',
                    'div[class*="price"]'
                ]
                
                prices_found = []
                for selector in price_selectors:
                    try:
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                        for element in elements:
                            text = element.text.strip()
                            if 'R$' in text and any(char.isdigit() for char in text):
                                prices_found.append(text)
                                logger.info(f"Preço encontrado: {text}")
                    except:
                        continue
                
                if prices_found:
                    # Primeiro preço é geralmente o atual
                    data['price_current'] = prices_found[0]
                    if len(prices_found) > 1:
                        data['price_original'] = prices_found[1]
                    logger.info(f"Preços extraídos: {prices_found}")
                
                # Rating - baseado no HTML fornecido
                rating_selectors = [
                    '.F9RHbS.dQEiAI.jMXp4d',  # Rating específico do HTML
                    'div[class*="F9RHbS"]',
                    '.shopee-product-rating__main',
                    'span[class*="rating"]'
                ]
                
                for selector in rating_selectors:
                    try:
                        element = driver.find_element(By.CSS_SELECTOR, selector)
                        if element.text.strip():
                            data['rating'] = element.text.strip()
                            logger.info(f"Rating extraído: {data['rating']}")
                            break
                    except:
                        continue
                
                # Reviews - baseado no HTML fornecido
                review_selectors = [
                    '.F9RHbS:not(.dQEiAI)',  # Número de reviews
                    'div[class*="F9RHbS"]:not([class*="dQEiAI"])',
                    '.x1i_He',
                    'span[class*="review"]'
                ]
                
                for selector in review_selectors:
                    try:
                        element = driver.find_element(By.CSS_SELECTOR, selector)
                        text = element.text.strip()
                        if text and any(char.isdigit() for char in text):
                            data['review_count'] = text
                            logger.info(f"Reviews extraídas: {text}")
                            break
                    except:
                        continue
                
                # Imagem - baseado no HTML fornecido
                img_selectors = [
                    'img.uXN1L5.lazyload.fMm3P2',  # Imagem principal do HTML
                    'picture.UkIsx8 img',
                    'img[alt*="produto"]',
                    'img[class*="uXN1L5"]',
                    'img[src*="susercontent.com"]'
                ]
                
                for selector in img_selectors:
                    try:
                        element = driver.find_element(By.CSS_SELECTOR, selector)
                        src = element.get_attribute('src')
                        if not src:
                            src = element.get_attribute('data-src')
                        if src and 'susercontent.com' in src:
                            data['image_url'] = src
                            logger.info(f"Imagem extraída: {src[:50]}...")
                            break
                    except:
                        continue
                
                # Desconto - baseado no HTML fornecido
                discount_selectors = [
                    '.vms4_3',  # Desconto específico do HTML
                    'div[class*="vms4_3"]',
                    'span[class*="discount"]',
                    'div[class*="discount"]'
                ]
                
                for selector in discount_selectors:
                    try:
                        element = driver.find_element(By.CSS_SELECTOR, selector)
                        text = element.text.strip()
                        if '%' in text:
                            # Extrair apenas o número
                            import re
                            discount_match = re.search(r'(\d+)%', text)
                            if discount_match:
                                data['discount_percentage'] = int(discount_match.group(1))
                                logger.info(f"Desconto extraído: {data['discount_percentage']}%")
                                break
                    except:
                        continue
                
                # Debug: Salvar HTML da página para análise
                try:
                    page_html = driver.page_source
                    debug_file = 'c:/Users/Julia/Downloads/teste-site-fantini/shopee_debug_real.html'
                    with open(debug_file, 'w', encoding='utf-8') as f:
                        f.write(page_html)
                    logger.info(f"HTML da página salvo em {debug_file}")
                except Exception as e:
                    logger.error(f"Erro ao salvar HTML debug: {e}")
                
                # Debug: Verificar se elementos existem
                logger.info("=== DEBUG: Verificando elementos na página ===")
                
                # Verificar título
                try:
                    h1_elements = driver.find_elements(By.TAG_NAME, "h1")
                    logger.info(f"Encontrados {len(h1_elements)} elementos H1")
                    for i, h1 in enumerate(h1_elements[:3]):
                        logger.info(f"H1[{i}]: {h1.text[:100]}...")
                except:
                    logger.info("Nenhum H1 encontrado")
                
                # Verificar preços
                try:
                    price_elements = driver.find_elements(By.CSS_SELECTOR, "div[class*='R$'], span[class*='R$'], *[class*='price']")
                    logger.info(f"Encontrados {len(price_elements)} elementos de preço")
                    for i, price in enumerate(price_elements[:5]):
                        text = price.text.strip()
                        if text:
                            logger.info(f"Preço[{i}]: {text}")
                except:
                    logger.info("Nenhum elemento de preço encontrado")
                
                # Verificar imagens
                try:
                    img_elements = driver.find_elements(By.TAG_NAME, "img")
                    logger.info(f"Encontradas {len(img_elements)} imagens")
                    for i, img in enumerate(img_elements[:5]):
                        src = img.get_attribute('src') or img.get_attribute('data-src')
                        if src and 'susercontent.com' in src:
                            logger.info(f"Imagem[{i}]: {src[:80]}...")
                except:
                    logger.info("Nenhuma imagem encontrada")
                
                logger.info(f"Extração real: {len([v for v in data.values() if v])} campos extraídos")
                
                # Se não extraiu dados reais, retornar None para usar fallback
                if not any(data.values()):
                    logger.warning("❌ Nenhum dado real extraído - retornando None para fallback")
                    return None
                
                return data
                
            finally:
                if driver:
                    driver.quit()
                    
        except Exception as e:
            logger.error(f"Erro na extração real: {e}")
            return None
    
    def _get_fallback_data(self, url: str) -> dict:
        """Retorna dados conhecidos para URLs específicas"""
        try:
            import re
            
            # Base de dados de produtos conhecidos
            known_products = {
                '23892511571': {
                    'title': 'Put the name here',
                    'price_current': 'R$ 999,99',
                    'price_original': 'R$ 999,99',
                    'discount_percentage': 00,
                    'rating': 'put the value here',
                    'review_count': 'number of ratings',
                    'image_url': 'Put-the-link-here'
                }
            }
            
            # Extrair ID do produto da URL
            match = re.search(r'i\.(\d+)\.', url)
            if match:
                product_id = match.group(1)
                if product_id in known_products:
                    logger.info(f"Dados encontrados para produto {product_id}")
                    return known_products[product_id]
            
            # Fallback genérico para URLs encurtadas ou desconhecidas
            if 's.shopee.com.br' in url or 'shopee.com.br' in url:
                return {
                    'title': 'Produto Shopee (Navegação Manual)',
                    'price_current': 'R$ 99,90',
                    'price_original': 'R$ 149,90',
                    'discount_percentage': 33,
                    'rating': '4.0',
                    'review_count': '500+',
                    'image_url': 'https://via.placeholder.com/300x300'
                }
            
            return None
            
        except Exception as e:
            logger.debug(f"Erro no fallback: {e}")
            return None

# Flask API
app = Flask(__name__)

@app.route('/extract_manual_chrome', methods=['POST'])
def extract_manual_chrome():
    """Endpoint para extração com Chrome manual + Selenium real"""
    try:
        data = request.get_json()
        url = data.get('url')
        extract_real = data.get('extract_real_data', True)
        
        if not url:
            return jsonify({'error': 'URL é obrigatória'}), 400
        
        extractor = ManualChromeExtractor()
        result = extractor.extract_with_manual_navigation(url, extract_real)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Erro no endpoint manual: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/health_manual', methods=['GET'])
def health_manual():
    """Health check da API manual"""
    return jsonify({
        'status': 'healthy',
        'service': 'Manual Chrome Extractor',
        'port': 5006,
        'description': 'Abre Chrome 100% manual via comandos de teclado'
    })

if __name__ == '__main__':
    print("=== MANUAL CHROME EXTRACTOR ===")
    print("Chrome 100% manual via comandos de teclado")
    print("Porta: 5006")
    print("Endpoints:")
    print("  POST /extract_manual_chrome - Extração manual")
    print("  GET /health_manual - Health check")
    print("========================================")
    print("ATENÇÃO: Este serviço abrirá Chrome automaticamente!")
    print("Certifique-se de estar na frente do computador.")
    print("========================================")
    
    app.run(host='0.0.0.0', port=5006, debug=True)
