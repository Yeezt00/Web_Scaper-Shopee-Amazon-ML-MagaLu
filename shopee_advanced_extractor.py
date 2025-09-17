#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import random
import json
import re
import logging
from typing import Dict, Optional
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, WebDriverException
import undetected_chromedriver as uc
from flask import Flask, request, jsonify
import requests
from bs4 import BeautifulSoup

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ShopeeAdvancedExtractor:
    """Extrator avançado do Shopee com técnicas anti-bot detection"""
    
    def __init__(self):
        self.driver = None
        self.wait = None
        
    def _create_manual_driver(self):
        """Cria driver Chrome manual visível para navegação humana"""
        try:
            options = webdriver.ChromeOptions()
            
            # Configurações para parecer usuário real
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            
            # User agent realista
            user_agents = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
            ]
            options.add_argument(f"--user-agent={random.choice(user_agents)}")
            
            # Janela visível com tamanho realista
            options.add_argument("--window-size=1366,768")
            
            try:
                self.driver = uc.Chrome(options=options)
                logger.info("Driver undetected-chrome criado com sucesso")
                options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
                
                self.driver = webdriver.Chrome(options=options)
                self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                self.wait = WebDriverWait(self.driver, 30)
                return True
                
            except Exception as e:
                logger.warning(f"Falha no undetected-chrome: {e}")
                # Fallback para Chrome normal
                try:
                    self.driver = webdriver.Chrome(options=options)
                    self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                    self.wait = WebDriverWait(self.driver, 20)
                    logger.info("Driver Chrome normal criado como fallback")
                    return True
                except Exception as e2:
                    logger.error(f"Erro ao criar driver fallback: {e2}")
                    return False
        except Exception as e:
            logger.error(f"Erro geral ao criar driver: {e}")
            return False
    
    def _simulate_keyboard_navigation(self):
        """Simula navegação manual intensiva com teclado e cursor para bypass de autenticação"""
        try:
            logger.info("Iniciando navegação manual intensiva com teclado...")
            
            # Aguardar página carregar
            time.sleep(5)
            
            # Simular Tab para navegar pelos elementos
            actions = ActionChains(self.driver)
            body = self.driver.find_element(By.TAG_NAME, "body")
            
            # Focar na página com clique
            body.click()
            time.sleep(2)
            
            # Navegação intensiva com Tab (simula usuário explorando)
            for _ in range(random.randint(8, 15)):
                actions.send_keys(Keys.TAB).perform()
                time.sleep(random.uniform(0.3, 0.8))
            
            # Scroll extensivo com Page Down
            for _ in range(random.randint(4, 8)):
                actions.send_keys(Keys.PAGE_DOWN).perform()
                time.sleep(random.uniform(1.5, 3.0))
            
            # Scroll para cima com Page Up
            for _ in range(random.randint(2, 4)):
                actions.send_keys(Keys.PAGE_UP).perform()
                time.sleep(random.uniform(1, 2))
            
            # Voltar ao topo com Home
            actions.send_keys(Keys.HOME).perform()
            time.sleep(2)
            
            # Simular Ctrl+F (busca) para parecer mais humano
            if random.random() < 0.5:
                actions.key_down(Keys.CONTROL).send_keys('f').key_up(Keys.CONTROL).perform()
                time.sleep(1)
                # Digitar algo e cancelar
                actions.send_keys('produto').perform()
                time.sleep(1)
                actions.send_keys(Keys.ESCAPE).perform()
                time.sleep(1)
            
            # Movimento extensivo e natural do mouse
            for _ in range(random.randint(6, 12)):
                x = random.randint(100, 1200)
                y = random.randint(100, 700)
                actions.move_to_element_with_offset(body, x, y).perform()
                time.sleep(random.uniform(0.5, 1.2))
                
                # Clique ocasional (sem afetar funcionalidade)
                if random.random() < 0.3:
                    actions.click().perform()
                    time.sleep(random.uniform(0.5, 1.0))
            
            # Scroll final com setas
            for _ in range(random.randint(5, 10)):
                actions.send_keys(Keys.ARROW_DOWN).perform()
                time.sleep(random.uniform(0.2, 0.5))
            
            logger.info("Navegação manual intensiva concluída")
            
        except Exception as e:
            logger.debug(f"Erro na simulação de teclado: {e}")
    
    def _bypass_authentication_prompt(self):
        """Tenta contornar prompt de autenticação com interação natural"""
        try:
            current_url = self.driver.current_url
            
            # Verificar se está em página de login/autenticação
            if any(keyword in current_url.lower() for keyword in ['login', 'auth', 'signin']):
                logger.info("Detectado prompt de autenticação - tentando contornar...")
                
                # Tentar voltar à página anterior
                self.driver.back()
                time.sleep(random.uniform(2, 4))
                
                # Se ainda estiver na página de login, tentar nova abordagem
                if any(keyword in self.driver.current_url.lower() for keyword in ['login', 'auth']):
                    # Abrir nova aba e tentar URL diretamente
                    self.driver.execute_script("window.open('');")
                    self.driver.switch_to.window(self.driver.window_handles[1])
                    time.sleep(1)
                    
                    return False  # Indica que precisa tentar nova URL
                
                return True
            
            return True
            
        except Exception as e:
            logger.debug(f"Erro no bypass de autenticação: {e}")
            return False
    
    def _wait_for_page_load(self):
        """Aguarda carregamento completo com tempo estendido para bypass de autenticação"""
        try:
            # Aguardar JavaScript carregar
            self.wait.until(lambda driver: driver.execute_script("return document.readyState") == "complete")
            
            # Aguardo inicial mais longo para bypass de autenticação
            logger.info("Aguardando carregamento completo da página...")
            time.sleep(8)
            
            # Aguardar elementos específicos do Shopee aparecerem
            selectors_to_wait = [
                '[data-testid="pdp-product-title"]',
                '.shopee-page-product__title',
                '.product-briefing__title',
                '.page-product__title',
                'h1[class*="title"]',
                'span[class*="title"]',
                'h1',
                '.title'
            ]
            
            element_found = False
            for selector in selectors_to_wait:
                try:
                    WebDriverWait(self.driver, 12).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    logger.info(f"Elemento principal encontrado: {selector}")
                    element_found = True
                    break
                except TimeoutException:
                    continue
            
            # Aguardar carregamento dinâmico de preços (AJAX) - tempo estendido
            price_selectors = [
                '[data-testid="pdp-price"]',
                '.shopee-page-product__price',
                '.product-price',
                'span[class*="price"]',
                'div[class*="price"]'
            ]
            
            # Aguardar até 25 segundos para preços aparecerem
            logger.info("Aguardando preços carregarem...")
            for attempt in range(25):
                price_found = False
                for selector in price_selectors:
                    try:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        for element in elements:
                            if 'R$' in element.text and any(char.isdigit() for char in element.text):
                                logger.info(f"Preço encontrado após {attempt + 1}s: {selector}")
                                price_found = True
                                break
                        if price_found:
                            break
                    except:
                        continue
                
                if price_found:
                    break
                    
                time.sleep(1)
            
            # Aguardo adicional para garantir carregamento completo
            logger.info("Aguardo final para estabilização...")
            time.sleep(5)
            
        except Exception as e:
            logger.debug(f"Erro ao aguardar carregamento: {e}")
    
    def _extract_title(self) -> Optional[str]:
        """Extrai título do produto com seletores otimizados"""
        selectors = [
            # Seletores específicos 2025
            '[data-testid="pdp-product-title"]',
            'span[data-testid="pdp-product-title"]',
            '.shopee-page-product__title',
            '.product-briefing__title',
            '.item-header__title',
            # Seletores genéricos mais amplos
            'h1[class*="title"]',
            'span[class*="title"]',
            'div[class*="title"]',
            '.shopee-product-rating__header__title',
            # Fallbacks
            'h1',
            'title'
        ]
        
        for selector in selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for element in elements:
                    text = element.text.strip()
                    if text and len(text) > 5 and 'Shopee' not in text and 'Login' not in text:
                        logger.info(f"Título extraído com '{selector}': {text[:50]}...")
                        return text
            except Exception as e:
                logger.debug(f"Erro no seletor de título '{selector}': {e}")
                continue
        
        return None
    
    def _extract_prices(self) -> Dict[str, Optional[str]]:
        """Extrai preços atual e original com seletores otimizados"""
        prices = {'current': None, 'original': None}
        
        # Seletores para preço atual (2025 - mais amplos)
        current_price_selectors = [
            '[data-testid="pdp-price"]',
            'span[data-testid="pdp-price"]',
            '.shopee-page-product__price .shopee-page-product__price__current',
            '.product-price__current-price',
            '.shopee-product-price__current-price',
            'span[class*="price"][class*="current"]',
            'div[class*="price"][class*="current"]',
            'span[class*="current-price"]',
            '.price-current',
            '.current-price',
            '._2v_e6C',
            '.shopee-page-product__price',
            # Seletores mais genéricos
            'span[class*="price"]:not([class*="original"])',
            'div[class*="price"]:not([class*="original"])'
        ]
        
        # Seletores para preço original
        original_price_selectors = [
            '.shopee-page-product__price .shopee-page-product__price__original',
            '.product-price__original-price',
            '.shopee-product-price__original-price',
            'span[class*="price"][class*="original"]',
            'div[class*="price"][class*="original"]',
            'span[class*="original-price"]',
            '.price-original',
            '.original-price',
            '._1w9jLI',
            # Seletores mais genéricos
            'span[class*="original"]',
            'div[class*="original"]'
        ]
        
        # Extrair preço atual
        for selector in current_price_selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for element in elements:
                    text = element.text.strip()
                    if 'R$' in text and any(char.isdigit() for char in text):
                        # Limpar e formatar preço
                        price_match = re.search(r'R\$\s*(\d+(?:[.,]\d+)*)', text)
                        if price_match:
                            price = f"R$ {price_match.group(1)}"
                            prices['current'] = price
                            logger.info(f"Preço atual extraído: {price}")
                            break
                if prices['current']:
                    break
            except Exception as e:
                logger.debug(f"Erro no seletor de preço atual '{selector}': {e}")
                continue
        
        # Extrair preço original
        for selector in original_price_selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for element in elements:
                    text = element.text.strip()
                    if 'R$' in text and any(char.isdigit() for char in text):
                        price_match = re.search(r'R\$\s*(\d+(?:[.,]\d+)*)', text)
                        if price_match:
                            price = f"R$ {price_match.group(1)}"
                            prices['original'] = price
                            logger.info(f"Preço original extraído: {price}")
                            break
                if prices['original']:
                    break
            except Exception as e:
                logger.debug(f"Erro no seletor de preço original '{selector}': {e}")
                continue
        
        return prices
    
    def _extract_rating_and_reviews(self) -> Dict[str, Optional[str]]:
        """Extrai rating e número de reviews"""
        data = {'rating': None, 'reviews': None}
        
        # Seletores para rating
        rating_selectors = [
            '[data-testid="pdp-review-summary-rating"]',
            '.shopee-product-rating__score',
            '.product-rating__score',
            '.rating-score',
            '.shopee-page-product__review .shopee-page-product__review__score'
        ]
        
        # Seletores para reviews
        review_selectors = [
            '[data-testid="pdp-review-summary-count"]',
            '.shopee-product-rating__count',
            '.product-rating__count',
            '.review-count',
            '.shopee-page-product__review .shopee-page-product__review__count'
        ]
        
        # Extrair rating
        for selector in rating_selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for element in elements:
                    text = element.text.strip()
                    rating_match = re.search(r'(\d+[.,]?\d*)', text)
                    if rating_match:
                        rating = float(rating_match.group(1).replace(',', '.'))
                        if 0 <= rating <= 5:
                            data['rating'] = rating
                            logger.info(f"Rating extraído: {rating}")
                            break
                if data['rating']:
                    break
            except Exception as e:
                logger.debug(f"Erro no seletor de rating '{selector}': {e}")
                continue
        
        # Extrair reviews
        for selector in review_selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for element in elements:
                    text = element.text.strip()
                    review_match = re.search(r'(\d+(?:[.,]?\d+)*(?:mil|k)?)', text, re.IGNORECASE)
                    if review_match:
                        data['reviews'] = review_match.group(1)
                        logger.info(f"Reviews extraídas: {data['reviews']}")
                        break
                if data['reviews']:
                    break
            except Exception as e:
                logger.debug(f"Erro no seletor de reviews '{selector}': {e}")
                continue
        
        return data
    
    def _extract_image(self) -> Optional[str]:
        """Extrai URL da imagem principal"""
        selectors = [
            '[data-testid="pdp-product-image"] img',
            '.shopee-page-product__gallery img',
            '.product-gallery__main img',
            '.gallery-main img',
            '.product-image img',
            'img[src*="shopee"]'
        ]
        
        for selector in selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for element in elements:
                    src = element.get_attribute('src')
                    if src and ('shopee' in src or 'cf.shopee' in src):
                        logger.info(f"Imagem extraída: {src[:50]}...")
                        return src
            except Exception as e:
                logger.debug(f"Erro no seletor de imagem '{selector}': {e}")
                continue
        
        return None
    
    def _detect_blocking(self) -> bool:
        """Detecta se a página foi bloqueada ou redirecionada"""
        try:
            current_url = self.driver.current_url
            page_source = self.driver.page_source.lower()
            
            # Verificar redirecionamentos suspeitos
            blocking_indicators = [
                'login' in current_url,
                'captcha' in current_url,
                'blocked' in current_url,
                'error' in current_url,
                'login' in page_source,
                'captcha' in page_source,
                'blocked' in page_source,
                'robot' in page_source,
                'verification' in page_source
            ]
            
            if any(blocking_indicators):
                logger.warning(f"Bloqueio detectado. URL atual: {current_url}")
                return True
                
            return False
            
        except Exception as e:
            logger.debug(f"Erro na detecção de bloqueio: {e}")
            return False

    def extract_product_data(self, url: str, use_native_chrome: bool = False) -> Dict:
        """Extrai dados do Shopee com navegação manual, Selenium ou Chrome nativo"""
        data = {
            'success': False,
            'title': None,
            'price_current': None,
            'price_original': None,
            'discount_percentage': None,
            'rating': None,
            'review_count': None,
            'image_url': None,
            'method_used': 'Manual Navigation with Keyboard',
            'extraction_time': 0,
            'url': url,
            'blocked': False,
            'auth_bypassed': False
        }
        
        start_time = time.time()
        
        # OPÇÃO 1: Chrome nativo sem automação detectável
        if use_native_chrome:
            logger.info("Usando Chrome nativo sem automação...")
            try:
                import requests
                response = requests.post(
                    'http://localhost:5005/open_native_chrome',
                    json={'url': url, 'method': 'keyboard', 'wait_time': 15},
                    timeout=30
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get('success'):
                        logger.info("Chrome nativo aberto com sucesso")
                        # Aplicar fallback já que não podemos extrair do Chrome nativo
                        fallback_data = self._get_fallback_data(url)
                        if fallback_data:
                            data.update(fallback_data)
                            data['success'] = True
                            data['method_used'] = 'Native Chrome + Fallback Database'
                            data['extraction_time'] = time.time() - start_time
                            logger.info("Chrome nativo + fallback aplicado")
                            return data
            except Exception as e:
                logger.warning(f"Erro com Chrome nativo: {e}")
        
        try:
            # OPÇÃO 2: Driver manual visível (Selenium)
            if not self._create_manual_driver():
                logger.warning("Falha ao criar driver manual - usando fallback direto")
                fallback_data = self._get_fallback_data(url)
                if fallback_data:
                    data.update(fallback_data)
                    data['success'] = True
                    data['method_used'] = 'Fallback Database Only'
                    data['extraction_time'] = time.time() - start_time
                    logger.info("Fallback aplicado diretamente")
                    return data
                else:
                    raise Exception("Falha ao criar driver manual e sem dados de fallback")
            
            logger.info(f"Navegação manual para: {url}")
            
            # Navegar para a página
            self.driver.get(url)
            
            # Aguardar carregamento inicial mais longo
            logger.info("Aguardando carregamento inicial...")
            time.sleep(8)
            
            # Primeira simulação de navegação (antes de verificar bloqueio)
            logger.info("Primeira simulação de navegação...")
            self._simulate_keyboard_navigation()
            
            # Verificar se precisa de autenticação após navegação
            if self._detect_blocking():
                logger.info("Detectada solicitação de autenticação - usando bypass manual...")
                data['blocked'] = True
                
                # Tentar bypass com navegação manual
                if self._bypass_authentication_prompt():
                    data['auth_bypassed'] = True
                    logger.info("Bypass de autenticação bem-sucedido")
                    
                    # Aguardar após bypass
                    time.sleep(5)
                else:
                    # Se não conseguiu bypass, continuar mesmo assim
                    logger.warning("Bypass não funcionou, continuando com extração...")
            
            # Aguardar carregamento dinâmico (tempo estendido)
            self._wait_for_page_load()
            
            # Segunda simulação de navegação para garantir
            logger.info("Segunda simulação de navegação...")
            self._simulate_keyboard_navigation()
            
            # Aguardo final antes da extração
            logger.info("Aguardo final antes da extração...")
            time.sleep(5)
            
            # Extrair dados
            logger.info("Iniciando extração com navegação manual...")
            
            # Debug: verificar se página carregou corretamente
            current_url = self.driver.current_url
            page_title = self.driver.title
            logger.info(f"URL atual: {current_url}")
            logger.info(f"Título da página: {page_title}")
            
            # Debug: verificar elementos na página
            try:
                all_text = self.driver.find_element(By.TAG_NAME, "body").text[:200]
                logger.info(f"Texto da página (primeiros 200 chars): {all_text}")
            except:
                logger.warning("Não foi possível obter texto da página")
            
            # Título
            data['title'] = self._extract_title()
            logger.info(f"Título extraído: {data['title']}")
            
            # Preços
            prices = self._extract_prices()
            data['price_current'] = prices['current']
            data['price_original'] = prices['original']
            logger.info(f"Preços extraídos - Atual: {data['price_current']}, Original: {data['price_original']}")
            
            # Calcular desconto
            if data['price_current'] and data['price_original']:
                try:
                    current = float(re.sub(r'[^\d,]', '', data['price_current']).replace(',', '.'))
                    original = float(re.sub(r'[^\d,]', '', data['price_original']).replace(',', '.'))
                    if original > current:
                        discount = round(((original - current) / original) * 100)
                        data['discount_percentage'] = discount
                except:
                    pass
            
            # Rating e reviews
            rating_data = self._extract_rating_and_reviews()
            data['rating'] = rating_data['rating']
            data['review_count'] = rating_data['reviews']
            
            # Imagem
            data['image_url'] = self._extract_image()
            
            # Verificar sucesso
            extracted_fields = sum(1 for v in [data['title'], data['price_current'], data['rating']] if v)
            data['success'] = extracted_fields >= 1
            
            # Se navegação manual falhou, tentar fallback com dados conhecidos
            if not data['success']:
                logger.info("Navegação manual falhou - tentando fallback com dados conhecidos...")
                fallback_data = self._get_fallback_data(url)
                if fallback_data:
                    data.update(fallback_data)
                    data['success'] = True
                    data['method_used'] = 'Manual Navigation + Fallback Database'
                    logger.info("Fallback aplicado com sucesso")
            
            data['extraction_time'] = time.time() - start_time
            
            logger.info(f"Extração manual concluída. Campos: {extracted_fields}/6, Sucesso: {data['success']}")
            
        except Exception as e:
            logger.error(f"Erro na extração manual: {e}")
            data['error'] = str(e)
            data['extraction_time'] = time.time() - start_time
            
        finally:
            if self.driver:
                try:
                    # Manter janela aberta por alguns segundos para debug
                    time.sleep(2)
                    self.driver.quit()
                except:
                    pass
        
        return data
    
    def _get_fallback_data(self, url: str) -> Dict:
        """Retorna dados conhecidos para URLs específicas como fallback"""
        try:
            # Base de dados de produtos conhecidos
            known_products = {
                
            }
            
            # Extrair ID do produto da URL
            import re
            match = re.search(r'i\.(\d+)\.', url)
            if match:
                product_id = match.group(1)
                if product_id in known_products:
                    logger.info(f"Dados de fallback encontrados para produto {product_id}")
                    return known_products[product_id]
            
            return None
            
        except Exception as e:
            logger.debug(f"Erro no fallback: {e}")
            return None

# Flask API
app = Flask(__name__)

@app.route('/extract_shopee_advanced', methods=['POST'])
def extract_shopee_advanced():
    """Endpoint para extração avançada do Shopee"""
    try:
        data = request.get_json()
        url = data.get('url')
        use_native_chrome = data.get('use_native_chrome', False)
        
        if not url:
            return jsonify({'error': 'URL é obrigatória'}), 400
        
        extractor = ShopeeAdvancedExtractor()
        result = extractor.extract_product_data(url, use_native_chrome=use_native_chrome)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500

@app.route('/extract_shopee_native', methods=['POST'])
def extract_shopee_native():
    """Endpoint específico para extração com Chrome nativo"""
    try:
        data = request.get_json()
        url = data.get('url')
        
        if not url:
            return jsonify({'error': 'URL é obrigatória'}), 400
        
        extractor = ShopeeAdvancedExtractor()
        result = extractor.extract_product_data(url, use_native_chrome=True)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500

@app.route('/health_advanced', methods=['GET'])
def health_advanced():
    """Health check da API avançada"""
    return jsonify({
        'service': 'Shopee Advanced Extractor',
        'status': 'running',
        'version': '2.0',
        'features': [
            'Undetected ChromeDriver',
            'Advanced Anti-Bot Detection',
            'Human Behavior Simulation',
            'Real-time Data Extraction',
            'Dynamic Price Detection'
        ]
    })

if __name__ == '__main__':
    print("=== SHOPEE ADVANCED EXTRACTOR ===")
    print("Extração real com técnicas anti-bot avançadas")
    print("Porta: 5004")
    print("Endpoint: /extract_shopee_advanced")
    print("=" * 40)
    
    app.run(host='0.0.0.0', port=5004, debug=True)
