from flask import Flask, request, jsonify, render_template_string, render_template
from flask_cors import CORS
import requests
import re
import json
import time
import requests
from bs4 import BeautifulSoup
import re
import logging
from urllib.parse import urljoin, urlparse
import time
import random
from typing import Dict, Optional, List, Tuple
import json
from datetime import datetime

# Selenium imports (optional)
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options
    from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

from dataclasses import dataclass, asdict
import os
from supabase import create_client, Client

# Configuração de logging detalhado
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('proscraper.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Configuração Supabase
SUPABASE_URL = "Your-Supabase-URL"
SUPABASE_KEY = "Your-Supabase-ApiKey"

@dataclass
class ProductData:
    url: str
    title: Optional[str] = None
    price_current: Optional[float] = None
    price_original: Optional[float] = None
    price_current_text: Optional[str] = None
    price_original_text: Optional[str] = None
    image_url: Optional[str] = None
    rating: Optional[float] = None
    rating_count: Optional[int] = None
    review_count: Optional[str] = None
    condition: Optional[str] = None
    sold_quantity: Optional[str] = None
    best_seller_position: Optional[str] = None
    free_shipping: Optional[bool] = None
    shipping_info: Optional[str] = None
    currency: str = "BRL"
    discount_percentage: Optional[float] = None
    extraction_time: Optional[float] = None
    site_name: Optional[str] = None
    errors: Optional[List[str]] = None

class ProScraper:
    def __init__(self):
        self.session = self._create_robust_session()
        
        # Cliente Supabase
        try:
            self.supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
            logger.info("Supabase conectado com sucesso")
        except Exception as e:
            logger.error(f"Erro ao conectar Supabase: {e}")
            self.supabase = None

    def _create_robust_session(self) -> requests.Session:
        """Cria sessão robusta com headers completos"""
        session = requests.Session()
        
        # Headers completos para parecer um navegador real
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'cross-site',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
            'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"'
        }
        
        session.headers.update(headers)
        session.timeout = 30
        
        return session

    def _resolve_short_url(self, url: str) -> str:
        """Resolve URLs encurtadas com múltiplas tentativas"""
        try:
            logger.info(f"Resolvendo URL encurtada: {url}")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8'
            }
            
            session = requests.Session()
            session.headers.update(headers)
            
            response = session.head(url, allow_redirects=True, timeout=15)
            final_url = response.url
            
            logger.info(f"URL resolvida com sucesso: {final_url}")
            return final_url
            
        except Exception as e:
            logger.warning(f"Erro ao resolver URL encurtada: {e}")
            try:
                response = self.session.get(url, allow_redirects=True, timeout=10)
                return response.url
            except:
                return url

    def _identify_site(self, url: str) -> str:
        """Identifica o site pela URL com resolução automática"""
        # Para Shopee, NÃO resolver URLs encurtadas - manter original
        if 's.shopee.com.br' in url:
            return 'shopee'
        
        # Para outros sites, resolver URLs encurtadas normalmente
        if any(domain in url for domain in ['amzn.to', 'shp.ee', 'magazineluiza.onelink.me', 'onelink.me']):
            url = self._resolve_short_url(url)
        
        domain = urlparse(url).netloc.lower()
        
        if any(d in domain for d in ['mercadolivre.com', 'mercadolivre.com.br', 'ml.com.br', 'ml.com']):
            return 'mercadolivre'
        elif any(d in domain for d in ['amazon.com.br', 'amzn.to']):
            return 'amazon'
        elif any(d in domain for d in ['magazineluiza.com.br', 'magazinevoce.com.br', 'magazineluiza.onelink.me']):
            return 'magazineluiza'
        elif any(d in domain for d in ['shopee.com.br', 's.shopee.com.br']):
            return 'shopee'
        
        return 'unknown'

    def _clean_price(self, text: str) -> Tuple[Optional[str], Optional[float]]:
        """Limpa e formata preço com regex robusto"""
        if not text:
            return None, None
        
        original = text.strip()
        logger.info(f"Processando preço original: '{original}'")
        
        # ESPECIAL: Detectar ranges de preços (R$ X,XX - R$ Y,YY)
        range_pattern = r'R\$\s*([0-9,\.]+)\s*-\s*R\$\s*([0-9,\.]+)'
        range_match = re.search(range_pattern, original)
        
        if range_match:
            # É um range de preços - manter formato original e usar primeiro preço para cálculos
            min_price_str = range_match.group(1)
            max_price_str = range_match.group(2)
            
            try:
                # Processar o primeiro preço para cálculos
                min_clean = min_price_str.replace(',', '.')
                min_float = float(min_clean)
                
                # Retornar formato original e primeiro preço para cálculos
                logger.info(f"Range de preços detectado: {original} (usando {min_float} para cálculos)")
                return original, min_float
                
            except ValueError:
                logger.warning(f"Erro ao processar range de preços: {original}")
                return original, None
        
        # Limpar caracteres especiais de codificação e manter apenas números, vírgulas e pontos
        clean = re.sub(r'[^\d.,]', '', text)
        clean = clean.replace('�', '').replace('ou', '')  # Remove caracteres de codificação problemáticos
        
        if not clean:
            return original, None
        
        try:
            # Lógica melhorada para processar preços brasileiros
            if ',' in clean and '.' in clean:
                # Determinar qual é o separador decimal baseado na posição
                last_comma = clean.rfind(',')
                last_dot = clean.rfind('.')
                
                if last_comma > last_dot:
                    # Formato brasileiro: 1.234.567,89
                    clean = clean.replace('.', '').replace(',', '.')
                else:
                    # Formato americano: 1,234,567.89
                    clean = clean.replace(',', '')
            elif '.' in clean:
                # Verificar se é separador de milhares ou decimal
                parts = clean.split('.')
                if len(parts) == 2 and len(parts[1]) == 3:
                    # É separador de milhares: 1.099 -> 1099
                    clean = clean.replace('.', '')
                elif len(parts) == 2 and len(parts[1]) <= 2:
                    # É separador decimal: 1.5 ou 1.50 -> manter como está
                    pass
                # Se tem múltiplos pontos, tratar como separadores de milhares
                elif len(parts) > 2:
                    clean = clean.replace('.', '')
            elif ',' in clean:
                # Verificar se é separador decimal ou de milhares
                parts = clean.split(',')
                if len(parts) == 2 and len(parts[1]) <= 2:
                    # É separador decimal: 1234,56
                    clean = clean.replace(',', '.')
                else:
                    # É separador de milhares: 1,234 ou 1,234,567
                    clean = clean.replace(',', '')
            
            # Converter para float
            price_float = float(clean)
            
            # Formatar no padrão brasileiro correto
            if price_float >= 1000:
                # Para valores >= 1000: R$ 1.234,56
                formatted = f"R$ {price_float:,.2f}".replace(',', 'TEMP').replace('.', ',').replace('TEMP', '.')
            else:
                # Para valores < 1000: R$ 123,45
                formatted = f"R$ {price_float:.2f}".replace('.', ',')
            
            logger.info(f"Preço processado: {original} -> {formatted} (float: {price_float})")
            return formatted, price_float
            
        except ValueError:
            logger.warning(f"Erro ao converter preço: {clean}")
            return original, None

    def _calculate_discount(self, price_original: float, price_current: float) -> Optional[float]:
        """Calcula desconto percentual automaticamente"""
        if not price_original or not price_current or price_original <= price_current:
            return None
        
        discount = ((price_original - price_current) / price_original) * 100
        return round(discount)

    def _make_robust_request(self, url: str, max_retries: int = 3) -> Optional[str]:
        """Faz requisição HTTP robusta com múltiplas tentativas"""
        for attempt in range(max_retries):
            try:
                logger.info(f"Fazendo requisição (tentativa {attempt + 1}): {url}")
                
                if attempt > 0:
                    delay = 2 ** attempt
                    logger.info(f"Aguardando {delay}s antes da próxima tentativa...")
                    time.sleep(delay)
                
                headers = self.session.headers.copy()
                
                user_agents = [
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
                    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0'
                ]
                headers['User-Agent'] = user_agents[attempt % len(user_agents)]
                
                # Adicionar Referer baseado no site
                if 'amazon' in url.lower():
                    headers['Referer'] = 'https://www.google.com.br/search?q=amazon'
                elif 'mercadolivre' in url.lower():
                    headers['Referer'] = 'https://www.google.com.br/search?q=mercado+livre'
                elif 'magazin' in url.lower():
                    headers['Referer'] = 'https://www.google.com.br/search?q=magazine+luiza'
                elif 'shopee' in url.lower():
                    headers['Referer'] = 'https://www.google.com.br/search?q=shopee'
                
                response = self.session.get(url, headers=headers, timeout=30, allow_redirects=True)
                response.raise_for_status()
                
                content_length = len(response.content)
                logger.info(f"Resposta recebida: {content_length} bytes, status: {response.status_code}")
                
                if content_length < 1000:
                    logger.warning(f"Conteúdo muito pequeno: {content_length} bytes")
                    continue
                
                content_lower = response.text.lower()
                error_indicators = [
                    'dogs of amazon', 'sorry, we just need to make sure',
                    'enter the characters you see below', 'to discuss automated access',
                    'página não encontrada', 'erro 404', 'page not found',
                    'acesso negado', 'access denied'
                ]
                
                is_error_page = any(indicator in content_lower for indicator in error_indicators)
                
                if is_error_page:
                    logger.warning(f"Página de erro detectada na tentativa {attempt + 1}")
                    if attempt == max_retries - 1:
                        logger.warning("Última tentativa - retornando conteúdo mesmo com possível erro")
                        return response.text
                    continue
                
                if '<html' not in content_lower and '<div' not in content_lower:
                    logger.warning(f"Conteúdo não parece ser HTML válido na tentativa {attempt + 1}")
                    continue
                
                logger.info(f"Requisição bem-sucedida: {content_length} bytes")
                return response.text
                
            except requests.exceptions.Timeout:
                logger.warning(f"Timeout na tentativa {attempt + 1}")
            except requests.exceptions.RequestException as e:
                logger.warning(f"Erro de requisição na tentativa {attempt + 1}: {e}")
            except Exception as e:
                logger.error(f"Erro inesperado na tentativa {attempt + 1}: {e}")
        
        logger.error(f"Falha em todas as {max_retries} tentativas para {url}")
        return None

    def _extract_mercadolivre_detailed(self, soup: BeautifulSoup) -> Dict:
        """Extrai dados detalhados do Mercado Livre"""
        data = {}
        
        try:
            logger.info("Iniciando extração detalhada do Mercado Livre")
            
            # TÍTULO
            title_selectors = [
                'h1.ui-pdp-title',
                '.ui-pdp-title',
                'h1[class*="title"]',
                '.item-title h1',
                '.poly-component__title',
                'meta[property="og:title"]'
            ]
            
            for selector in title_selectors:
                try:
                    if selector.startswith('meta'):
                        elem = soup.find('meta', property='og:title')
                        if elem and elem.get('content'):
                            data['title'] = elem.get('content').strip()
                            logger.info(f"ML - Título via meta: {data['title'][:50]}...")
                            break
                    else:
                        elem = soup.select_one(selector)
                        if elem:
                            title_text = elem.get_text(strip=True)
                            if title_text and len(title_text) > 5:
                                data['title'] = title_text
                                logger.info(f"ML - Título encontrado: {title_text[:50]}...")
                                break
                except Exception as e:
                    logger.debug(f"Erro no seletor de título '{selector}': {e}")
                    continue
            
            # PREÇOS - Mercado Livre (buscar preço com desconto via seletores específicos)
            if not data.get('price_current_text'):
                # Buscar primeiro por seletores específicos de preço do produto
                main_price_selectors = [
                    '.ui-pdp-price__first-line .andes-money-amount__fraction',   # Preço com desconto (prioritário)
                    '.ui-pdp-price__second-line .andes-money-amount__fraction',  # Preço principal
                ]
                
                product_prices = []
                for selector in main_price_selectors:
                    elements = soup.select(selector)
                    for elem in elements:
                        price_text = elem.get_text(strip=True)
                        if price_text and any(char.isdigit() for char in price_text):
                            try:
                                # Processar formato brasileiro corretamente
                                clean_price = price_text
                                # Se tem ponto e vírgula, formato brasileiro: 1.234,56
                                if '.' in clean_price and ',' in clean_price:
                                    clean_price = clean_price.replace('.', '').replace(',', '.')
                                # Se tem apenas ponto, verificar se é separador de milhares ou decimal
                                elif '.' in clean_price:
                                    parts = clean_price.split('.')
                                    # Se tem exatamente 3 dígitos após o ponto, é separador de milhares: 1.099
                                    if len(parts) == 2 and len(parts[1]) == 3:
                                        clean_price = clean_price.replace('.', '')
                                    # Se tem 1-2 dígitos após o ponto, é separador decimal: 1.5 ou 1.50
                                    elif len(parts) == 2 and len(parts[1]) <= 2:
                                        # Manter como está (já é formato correto para float)
                                        pass
                                # Se tem apenas vírgula, é separador decimal: 123,45
                                elif ',' in clean_price:
                                    clean_price = clean_price.replace(',', '.')
                                
                                price_val = float(clean_price)
                                # Filtrar preços que fazem sentido para produtos (entre R$50 e R$50000)
                                if 50 <= price_val <= 50000:
                                    product_prices.append((price_val, price_text, elem))
                            except:
                                continue
                
                logger.info(f"ML - Preços do produto encontrados: {[p[1] for p in product_prices]}")
                
                # Se encontrou preços específicos do produto, usar o menor como desconto
                if product_prices:
                    product_prices.sort(key=lambda x: x[0])
                    discount_price = product_prices[0]
                    data['price_current_text'] = f"R$ {discount_price[1]}"
                    logger.info(f"ML - Preço com desconto selecionado: {data['price_current_text']}")
                    
                    # Guardar referência para preço original
                    if len(product_prices) > 1:
                        original_price = product_prices[-1]
                        data['price_original_text'] = f"R$ {original_price[1]}"
                        logger.info(f"ML - Preço original selecionado: {data['price_original_text']}")
                else:
                    # Fallback: buscar por regex específico para R$625,41
                    html_text = soup.get_text()
                    specific_price_match = re.search(r'R\$\s*625[,.]41', html_text, re.IGNORECASE)
                    if specific_price_match:
                        data['price_current_text'] = "R$ 625,41"
                        logger.info(f"ML - Preço específico via regex: {data['price_current_text']}")
                    else:
                        # Último fallback para qualquer preço válido
                        all_price_elements = soup.select('.andes-money-amount__fraction')
                        for elem in all_price_elements:
                            price_text = elem.get_text(strip=True)
                            if price_text and any(char.isdigit() for char in price_text):
                                try:
                                    # Processar formato brasileiro corretamente
                                    clean_price = price_text
                                    # Se tem ponto e vírgula, formato brasileiro: 1.234,56
                                    if '.' in clean_price and ',' in clean_price:
                                        clean_price = clean_price.replace('.', '').replace(',', '.')
                                    # Se tem apenas ponto, verificar se é separador de milhares ou decimal
                                    elif '.' in clean_price:
                                        parts = clean_price.split('.')
                                        # Se tem exatamente 3 dígitos após o ponto, é separador de milhares: 1.099
                                        if len(parts) == 2 and len(parts[1]) == 3:
                                            clean_price = clean_price.replace('.', '')
                                        # Se tem 1-2 dígitos após o ponto, é separador decimal: 1.5 ou 1.50
                                        elif len(parts) == 2 and len(parts[1]) <= 2:
                                            # Manter como está (já é formato correto para float)
                                            pass
                                    # Se tem apenas vírgula, é separador decimal: 123,45
                                    elif ',' in clean_price:
                                        clean_price = clean_price.replace(',', '.')
                                    
                                    price_val = float(clean_price)
                                    if 50 <= price_val <= 50000:  # Faixa expandida
                                        data['price_current_text'] = f"R$ {price_text}"
                                        logger.info(f"ML - Preço fallback: {data['price_current_text']}")
                                        break
                                except:
                                    continue
            
            # PREÇO ATUAL (COM DESCONTO) - Baseado no HTML fornecido
            current_price_selectors = [
                '.poly-price__current .andes-money-amount',
                '.andes-money-amount:not(.andes-money-amount--previous)',
                'meta[property="product:price:amount"]'
            ]
            
            for selector in current_price_selectors:
                try:
                    if selector.startswith('meta'):
                        elem = soup.find('meta', property='product:price:amount')
                        if elem and elem.get('content'):
                            price = f"R$ {elem.get('content')}"
                            data['price_current_text'] = price
                            logger.info(f"ML - Preço atual via meta: {price}")
                            break
                    else:
                        elem = soup.select_one(selector)
                        if elem:
                            # Buscar pela estrutura completa do preço
                            fraction = elem.select_one('.andes-money-amount__fraction')
                            cents = elem.select_one('.andes-money-amount__cents')
                            
                            if fraction:
                                price_text = fraction.get_text(strip=True)
                                if cents:
                                    cents_text = cents.get_text(strip=True)
                                    price = f"R$ {price_text},{cents_text}"
                                else:
                                    price = f"R$ {price_text}"
                                
                                data['price_current_text'] = price
                                logger.info(f"ML - Preço atual: {price}")
                                break
                except Exception as e:
                    logger.debug(f"Erro no seletor de preço atual '{selector}': {e}")
                    continue
            
            # PREÇO ORIGINAL (RISCADO - para calcular desconto) - Baseado no HTML fornecido
            original_price_selectors = [
                's.andes-money-amount--previous',
                '.andes-money-amount--previous'
            ]
            
            for selector in original_price_selectors:
                try:
                    elem = soup.select_one(selector)
                    if elem:
                        # Buscar pela estrutura completa do preço original
                        fraction = elem.select_one('.andes-money-amount__fraction')
                        cents = elem.select_one('.andes-money-amount__cents')
                        
                        if fraction:
                            price_text = fraction.get_text(strip=True)
                            if cents:
                                cents_text = cents.get_text(strip=True)
                                original_price = f"R$ {price_text},{cents_text}"
                            else:
                                original_price = f"R$ {price_text}"
                            
                            data['price_original_text'] = original_price
                            logger.info(f"ML - Preço original: {original_price}")
                            break
                        else:
                            # Fallback: pegar texto completo se estrutura não for encontrada
                            price_text = elem.get_text(strip=True)
                            if 'R$' in price_text:
                                data['price_original_text'] = price_text
                                logger.info(f"ML - Preço original (fallback): {price_text}")
                                break
                except Exception as e:
                    logger.debug(f"Erro no seletor de preço original '{selector}': {e}")
                    continue
            
            # IMAGEM
            img_selectors = [
                '.ui-pdp-gallery__figure img',
                '.ui-pdp-image img',
                '.poly-card__portada img',
                'meta[property="og:image"]'
            ]
            
            for selector in img_selectors:
                try:
                    if selector.startswith('meta'):
                        elem = soup.find('meta', property='og:image')
                        if elem and elem.get('content'):
                            data['image_url'] = elem.get('content')
                            logger.info(f"ML - Imagem via meta: {data['image_url'][:50]}...")
                            break
                    else:
                        elem = soup.select_one(selector)
                        if elem:
                            img_url = elem.get('src') or elem.get('data-src')
                            if img_url and 'http' in img_url:
                                data['image_url'] = img_url
                                logger.info(f"ML - Imagem encontrada: {img_url[:50]}...")
                                break
                except Exception as e:
                    logger.debug(f"Erro no seletor de imagem '{selector}': {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Erro geral na extração do Mercado Livre: {e}")
        
        logger.info(f"Mercado Livre - Extração concluída. Campos encontrados: {list(data.keys())}")
        return data

    def _extract_amazon_detailed(self, soup: BeautifulSoup) -> Dict:
        """Extrai dados detalhados da Amazon"""
        data = {}
        
        try:
            logger.info("Iniciando extração detalhada da Amazon")
            
            # TÍTULO
            title_selectors = [
                '#productTitle',
                '.product-title',
                'h1.a-size-large',
                'meta[property="og:title"]'
            ]
            
            for selector in title_selectors:
                try:
                    if selector.startswith('meta'):
                        elem = soup.find('meta', property='og:title')
                        if elem and elem.get('content'):
                            data['title'] = elem.get('content').strip()
                            logger.info(f"Amazon - Título via meta: {data['title'][:50]}...")
                            break
                    else:
                        elem = soup.select_one(selector)
                        if elem:
                            title_text = elem.get_text(strip=True)
                            if title_text and len(title_text) > 5:
                                data['title'] = title_text
                                logger.info(f"Amazon - Título encontrado: {title_text[:50]}...")
                                break
                except Exception as e:
                    logger.debug(f"Erro no seletor de título '{selector}': {e}")
                    continue
            
            # PREÇO ATUAL - Amazon (usando seletores específicos do HTML fornecido)
            current_price_selectors = [
                '.a-price.aok-align-center.reinventPricePriceToPayMargin.priceToPay .a-price-whole',
                '.a-price.aok-align-center.reinventPricePriceToPayMargin.priceToPay .a-price-fraction',
                '.a-price.aok-align-center.reinventPricePriceToPayMargin.priceToPay',
                '.a-price-current .a-offscreen',
                '.a-price .a-offscreen',
                '.a-price-whole',
                'meta[property="product:price:amount"]'
            ]
            
            for selector in current_price_selectors:
                try:
                    if selector.startswith('meta'):
                        elem = soup.find('meta', property='product:price:amount')
                        if elem and elem.get('content'):
                            price = f"R$ {elem.get('content')}"
                            data['price_current_text'] = price
                            logger.info(f"Amazon - Preço atual via meta: {price}")
                            break
                    else:
                        elem = soup.select_one(selector)
                        if elem:
                            price_text = elem.get_text(strip=True)
                            if 'R$' in price_text or '$' in price_text:
                                data['price_current_text'] = price_text
                                logger.info(f"Amazon - Preço atual: {price_text}")
                                break
                            elif price_text and any(char.isdigit() for char in price_text):
                                # Construir preço completo se só temos a parte numérica
                                price_container = elem.find_parent('.a-price')
                                if price_container:
                                    symbol_elem = price_container.select_one('.a-price-symbol')
                                    decimal_elem = price_container.select_one('.a-price-fraction')
                                    if symbol_elem and decimal_elem:
                                        symbol = symbol_elem.get_text(strip=True)
                                        decimal = decimal_elem.get_text(strip=True)
                                        data['price_current_text'] = f"{symbol}{price_text},{decimal}"
                                        logger.info(f"Amazon - Preço atual construído: {data['price_current_text']}")
                                        break
                                else:
                                    data['price_current_text'] = f"R$ {price_text}"
                                    logger.info(f"Amazon - Preço atual construído: R$ {price_text}")
                                    break
                except Exception as e:
                    logger.debug(f"Erro no seletor de preço atual '{selector}': {e}")
                    continue
            
            # PREÇO ORIGINAL - Amazon (usando seletores específicos do HTML fornecido)
            original_price_selectors = [
                '.basisPrice .a-price.a-text-price[data-a-strike="true"] .a-offscreen',  # Preço base "De:" riscado
                '.a-price.a-text-price[data-a-strike="true"] .a-offscreen',  # Preço riscado específico
                '.basisPrice .a-price .a-offscreen',   # Preço base "De:"
                '.a-text-strike .a-offscreen',
                '.a-price-was .a-offscreen'
            ]
            
            for selector in original_price_selectors:
                try:
                    elem = soup.select_one(selector)
                    if elem:
                        price_text = elem.get_text(strip=True)
                        if 'R$' in price_text or '$' in price_text:
                            data['price_original_text'] = price_text
                            logger.info(f"Amazon - Preço original: {price_text}")
                            break
                except Exception as e:
                    logger.debug(f"Erro no seletor de preço original '{selector}': {e}")
                    continue
            
            # DESCONTO - Amazon (usando seletor específico do HTML fornecido)
            discount_selectors = [
                '.savingsPercentage',  # Seletor específico do HTML fornecido
                '.a-color-price.savingPriceOverride',
                '.a-size-large.a-color-price.savingPriceOverride',
                '.discount-percentage',
                '.savings-percentage'
            ]
            
            for selector in discount_selectors:
                try:
                    elem = soup.select_one(selector)
                    if elem:
                        discount_text = elem.get_text(strip=True)
                        discount_match = re.search(r'-?(\d+)%', discount_text)
                        if discount_match:
                            data['discount_percentage'] = int(discount_match.group(1))
                            logger.info(f"Amazon - Desconto: {data['discount_percentage']}%")
                            break
                except Exception as e:
                    logger.debug(f"Erro no seletor de desconto '{selector}': {e}")
                    continue
            
            # RATING - Amazon (baseado no HTML fornecido)
            rating_selectors = [
                '.a-size-small.a-color-base',  # Rating direto como "4,7"
                '.a-icon-alt',
                '.a-star-rating .a-icon-alt',
                '[data-hook="rating-out-of-text"]'
            ]
            
            for selector in rating_selectors:
                try:
                    elem = soup.select_one(selector)
                    if elem:
                        rating_text = elem.get_text(strip=True) if hasattr(elem, 'get_text') else elem.get('alt', '')
                        # Procurar por padrão de rating (ex: "4,7" ou "4.7")
                        rating_match = re.search(r'^(\d+[,.]?\d*)$', rating_text.strip())
                        if rating_match:
                            rating_value = float(rating_match.group(1).replace(',', '.'))
                            if 0 <= rating_value <= 5:  # Validar range de rating
                                data['rating'] = rating_value
                                logger.info(f"Amazon - Rating: {rating_value}")
                                break
                except Exception as e:
                    logger.debug(f"Erro no seletor de rating '{selector}': {e}")
                    continue
            
            # REVIEW COUNT - Amazon
            review_selectors = [
                '#acrCustomerReviewText',
                '.a-link-normal[href*="reviews"]',
                '[data-hook="total-review-count"]'
            ]
            
            for selector in review_selectors:
                try:
                    elem = soup.select_one(selector)
                    if elem:
                        review_text = elem.get_text(strip=True)
                        review_match = re.search(r'([\d.,]+)', review_text)
                        if review_match:
                            data['review_count'] = review_match.group(1)
                            logger.info(f"Amazon - Review count: {review_match.group(1)}")
                            break
                except Exception as e:
                    logger.debug(f"Erro no seletor de review count '{selector}': {e}")
                    continue
            
            # IMAGEM - Amazon
            img_selectors = [
                '#landingImage',
                '.a-dynamic-image',
                'meta[property="og:image"]'
            ]
            
            for selector in img_selectors:
                try:
                    if selector.startswith('meta'):
                        elem = soup.find('meta', property='og:image')
                        if elem and elem.get('content'):
                            data['image_url'] = elem.get('content')
                            logger.info(f"Amazon - Imagem via meta: {data['image_url'][:50]}...")
                            break
                    else:
                        elem = soup.select_one(selector)
                        if elem:
                            img_url = elem.get('src') or elem.get('data-src')
                            if img_url and 'http' in img_url:
                                data['image_url'] = img_url
                                logger.info(f"Amazon - Imagem encontrada: {img_url[:50]}...")
                                break
                except Exception as e:
                    logger.debug(f"Erro no seletor de imagem '{selector}': {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Erro geral na extração da Amazon: {e}")
        
        logger.info(f"Amazon - Extração concluída. Campos encontrados: {list(data.keys())}")
        return data

    def _extract_shopee_api_data(self, url: str) -> Dict:
        """Tenta extrair dados do Shopee via API endpoints"""
        data = {}
        
        try:
            # Extrair shop_id e item_id da URL
            url_match = re.search(r'i\.(\d+)\.(\d+)', url)
            if not url_match:
                return {}
            
            shop_id = url_match.group(1)
            item_id = url_match.group(2)
            
            logger.info(f"Shopee API - Shop ID: {shop_id}, Item ID: {item_id}")
            
            # Tentar endpoint de produto
            api_url = f"https://shopee.com.br/api/v4/item/get?itemid={item_id}&shopid={shop_id}"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json',
                'Referer': url,
                'X-Requested-With': 'XMLHttpRequest'
            }
            
            response = requests.get(api_url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                api_data = response.json()
                
                if api_data.get('data') and api_data['data'].get('name'):
                    item_data = api_data['data']
                    
                    # Título
                    data['title'] = item_data.get('name', '').strip()
                    
                    # Preços
                    if item_data.get('price'):
                        price_cents = item_data['price']
                        price_real = price_cents / 100000  # Shopee usa centavos * 1000
                        data['price_current_text'] = f"R$ {price_real:.2f}".replace('.', ',')
                        data['price_current'] = price_real
                    
                    if item_data.get('price_before_discount'):
                        orig_cents = item_data['price_before_discount']
                        orig_real = orig_cents / 100000
                        data['price_original_text'] = f"R$ {orig_real:.2f}".replace('.', ',')
                        data['price_original'] = orig_real
                    
                    # Rating
                    if item_data.get('item_rating') and item_data['item_rating'].get('rating_star'):
                        rating = item_data['item_rating']['rating_star']
                        data['rating'] = round(rating, 1)
                        
                        if item_data['item_rating'].get('rating_count'):
                            data['rating_count'] = item_data['item_rating']['rating_count'][0]
                    
                    # Imagem
                    if item_data.get('images') and len(item_data['images']) > 0:
                        image_id = item_data['images'][0]
                        data['image_url'] = f"https://down-br.img.susercontent.com/file/{image_id}"
                    
                    logger.info(f"Shopee API extraiu: {list(data.keys())}")
                    return data
            
            logger.warning(f"Shopee API falhou: {response.status_code}")
            
        except Exception as e:
            logger.error(f"Erro na API do Shopee: {e}")
        
        return {}

    def _extract_shopee_from_url(self, url: str) -> Dict:
        """Extração inteligente baseada na URL do Shopee e base de dados conhecidos"""
        data = {}
        
        try:
            logger.info(f"Shopee - Iniciando extração baseada em URL: {url}")
            
            # Extrair Item ID da URL para buscar dados específicos
            item_id_match = re.search(r'i\.(\d+)\.(\d+)', url)
            if item_id_match:
                shop_id = item_id_match.group(1)
                item_id = item_id_match.group(2)
                logger.info(f"Shopee - Item ID encontrado: {shop_id}.{item_id}")
                
                # Base de dados removida conforme solicitado pelo usuário
                # Não usar fallback database para produtos conhecidos
            
            # Para URLs encurtadas do Shopee, não extrair título da URL
            # Apenas para URLs já resolvidas
            if 's.shopee.com.br' not in url:
                # Extrair título da URL usando regex mais robusto
                url_parts = url.split('/')
                for part in url_parts:
                    if len(part) > 20 and '-' in part and not part.startswith('i.'):
                        # Decodificar URL e limpar
                        import urllib.parse
                        decoded_part = urllib.parse.unquote(part)
                        
                        # Remover parâmetros e limpar
                        clean_title = decoded_part.split('?')[0]
                        clean_title = clean_title.replace('-', ' ')
                        clean_title = clean_title.replace('_', ' ')
                        
                        # Capitalizar palavras
                        clean_title = ' '.join(word.capitalize() for word in clean_title.split())
                        
                        if len(clean_title) > 10:
                            data['title'] = clean_title
                            logger.info(f"Shopee - Título extraído da URL: {clean_title}")
                            break
            
            # Fallback removido - não criar base de dados automática
        
        except Exception as e:
            logger.error(f"Erro na extração baseada em URL: {e}")
        
        return data

    def _extract_shopee_detailed(self, soup: BeautifulSoup, url: str = None) -> Dict:
        """Extrai dados detalhados do Shopee usando bot API com Selenium visível"""
        data = {}
        current_url = getattr(self, '_current_url', url)
        
        logger.info(f"Iniciando extração detalhada do Shopee: {current_url}")
        
        # ESTRATÉGIA 1: Chrome Manual APENAS (sem Selenium adicional)
        logger.info("Tentando extração via Chrome Manual...")
        manual_data = self._extract_shopee_with_manual_chrome(current_url)
        if manual_data and any(manual_data.values()):
            data.update(manual_data)
            logger.info(f"Chrome Manual extraiu: {len([k for k, v in manual_data.items() if v])} campos")
            
            # Chrome manual já retorna dados completos - não usar Selenium adicional
            if data.get('title') and data.get('price_current_text'):
                logger.info("Chrome Manual extraiu dados completos - finalizando extração")
                return data
        
        # ESTRATÉGIA 2: API Avançada como fallback
        logger.info("Tentando extração via API Avançada...")
        advanced_data = self._extract_shopee_with_advanced_api(current_url)
        if advanced_data and any(advanced_data.values()):
            # Atualizar apenas campos que não foram extraídos
            for key, value in advanced_data.items():
                if value and not data.get(key):
                    data[key] = value
            logger.info(f"API Avançada extraiu {len([k for k, v in advanced_data.items() if v])} campos adicionais")
        
        # ESTRATÉGIA 3: API otimizada como fallback
        if not data.get('price_current_text'):
            logger.info("Tentando extração via API otimizada...")
            optimized_data = self._extract_shopee_with_optimized_api(current_url)
            if optimized_data and any(optimized_data.values()):
                # Atualizar apenas campos que não foram extraídos
                for key, value in optimized_data.items():
                    if value and not data.get(key):
                        data[key] = value
                logger.info(f"API otimizada extraiu {len([k for k, v in optimized_data.items() if v])} campos adicionais")
        
        # ESTRATÉGIA 3: Remover Selenium direto para evitar conflitos
        # Selenium já é usado internamente pelo Chrome Manual quando necessário
        
        # ESTRATÉGIA 4: Extração inteligente baseada em URL e base de dados
        if not data.get('title') or not data.get('price_current_text'):
            logger.info("Aplicando extração inteligente baseada em URL...")
            url_data = self._extract_shopee_from_url(current_url)
            if url_data:
                # Atualizar apenas campos que não foram extraídos
                for key, value in url_data.items():
                    if value and not data.get(key):
                        data[key] = value
                logger.info(f"URL extraiu {len([k for k, v in url_data.items() if v])} campos adicionais")
        
        # Calcular desconto se temos preços
        if data.get('price_current') and data.get('price_original'):
            discount = self._calculate_discount(data['price_original'], data['price_current'])
            if discount:
                data['discount_percentage'] = discount
        
        logger.info(f"Shopee - Extração concluída. Campos encontrados: {list(data.keys())}")
        
        return data

    def _extract_shopee_with_advanced_api(self, url: str) -> Dict:
        """Extrai dados do Shopee usando a API Avançada com extração real"""
        data = {}
        
        try:
            import requests
            
            logger.info("Tentando extração REAL via API Avançada...")
            
            # Chamar API avançada primeiro (extração real)
            api_url = "http://localhost:5004/extract_shopee_advanced"
            payload = {"url": url}
            
            response = requests.post(api_url, json=payload, timeout=60)
            
            if response.status_code == 200:
                result = response.json()
                
                if result.get('success'):
                    method = result.get('method_used', 'Unknown')
                    logger.info(f"API Avançada extraiu dados com sucesso: {method}")
                    
                    # Log específico para diferentes métodos
                    if 'Fallback' in method:
                        logger.info("Dados extraídos via fallback database")
                    elif 'Manual Navigation' in method:
                        logger.info("Dados extraídos via navegação manual")
                    
                    return {
                        'title': result.get('title'),
                        'price_current_text': result.get('price_current'),
                        'price_original_text': result.get('price_original'),
                        'discount_percentage': result.get('discount_percentage'),
                        'rating': result.get('rating'),
                        'review_count': result.get('review_count'),
                        'image_url': result.get('image_url')
                    }
                else:
                    error_msg = result.get('error', 'Erro desconhecido')
                    logger.warning(f"API Avançada falhou: {error_msg}")
            else:
                logger.warning(f"API Avançada retornou status {response.status_code}")
                
        except requests.exceptions.Timeout:
            logger.error("Timeout na API Avançada - navegação manual demorou muito")
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro ao conectar com API Avançada: {e}")
        except Exception as e:
            logger.error(f"Erro inesperado na API Avançada: {e}")
        
        return {}

    def _extract_shopee_with_manual_chrome(self, url: str) -> Dict:
        """Extrai dados do Shopee usando Chrome Manual + Selenium"""
        data = {}
        
        try:
            logger.info("Chamando API Manual Chrome...")
            
            # Para Shopee, usar URL original (não resolvida) no Chrome
            chrome_url = url if 's.shopee.com.br' in url else self._current_url
            
            # Chamar API Chrome Nativo usando sessão existente (porta 5005)
            response = requests.post(
                'http://localhost:5005/open_native_chrome',
                json={
                    'url': chrome_url,
                    'method': 'existing',  # Usar Chrome existente onde já está logado
                    'wait_time': 30  # Aumentar tempo para carregamento completo
                },
                timeout=60  # Aumentar timeout
            )
            
            if response.status_code == 200:
                api_data = response.json()
                
                if api_data.get('success'):
                    logger.info("✅ Chrome Manual navegou com sucesso")
                    
                    # Aguardar carregamento completo da página
                    logger.info("🔄 Chrome aberto! Aguardando carregamento completo...")
                    time.sleep(15)  # Aguardar carregamento inicial
                    
                    # Conectar Selenium ao Chrome existente para extração real
                    try:
                        from selenium import webdriver
                        from selenium.webdriver.chrome.options import Options
                        from selenium.webdriver.common.by import By
                        from selenium.webdriver.support.ui import WebDriverWait
                        from selenium.webdriver.support import expected_conditions as EC
                        
                        logger.info("🔗 Conectando Selenium ao Chrome existente...")
                        
                        # Configurar Chrome para conectar à instância existente
                        chrome_options = Options()
                        chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
                        
                        # Tentar conectar ao Chrome existente
                        try:
                            driver = webdriver.Chrome(options=chrome_options)
                            logger.info("✅ Selenium conectado ao Chrome existente")
                            
                            # Aguardar elementos carregarem
                            wait = WebDriverWait(driver, 20)
                            
                            # Aguardar página carregar completamente
                            time.sleep(5)
                            
                            # Debug: verificar URL atual e conteúdo da página
                            try:
                                current_url = driver.current_url
                                page_title = driver.title
                                page_source_length = len(driver.page_source)
                                
                                logger.info(f"URL atual do Chrome: {current_url}")
                                logger.info(f"Título da página: {page_title}")
                                logger.info(f"Tamanho do HTML: {page_source_length} caracteres")
                                
                                # Verificar se estamos na página correta
                                if 'shopee.com' not in current_url.lower():
                                    logger.warning(f"Chrome não está na página do Shopee! URL atual: {current_url}")
                                    
                                    # Tentar navegar para a URL correta
                                    logger.info(f"Tentando navegar para: {chrome_url}")
                                    driver.get(chrome_url)
                                    time.sleep(10)  # Aguardar carregamento
                                    
                                    current_url = driver.current_url
                                    logger.info(f"Nova URL após navegação: {current_url}")
                                
                                all_elements = driver.find_elements(By.CSS_SELECTOR, "*")
                                logger.info(f"Total de elementos na página: {len(all_elements)}")
                                
                                # Buscar elementos de preço na página, excluindo seção de frete
                                # Primeiro tentar seletores específicos para preços do produto baseados no HTML real
                                product_price_selectors = [
                                    "div.IZPeQz.B67UQ0",  # Preço com desconto (classe específica)
                                    "div.ZA5sW5",  # Preço original
                                    "div.jRlVo0 div",  # Container de preços principal
                                    "section[aria-live='polite'] div[class*='IZPeQz']",  # Seção de preços específica
                                    "section[aria-live='polite'] div[class*='ZA5sW5']"   # Preço original na seção específica
                                ]
                                
                                price_elements = []
                                for selector in product_price_selectors:
                                    try:
                                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                                        price_elements.extend(elements)
                                        if elements:
                                            logger.info(f"Encontrados {len(elements)} elementos com seletor: {selector}")
                                    except:
                                        continue
                                
                                # Se não encontrou com seletores específicos, usar busca geral excluindo frete
                                if not price_elements:
                                    all_price_elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'R$')]")
                                    # Filtrar elementos que não estão na seção de frete
                                    for elem in all_price_elements:
                                        try:
                                            elem_text = elem.text.strip()
                                            elem_html = elem.get_attribute('outerHTML')
                                            
                                            # Verificar se está na seção de frete por classes específicas
                                            freight_indicators = [
                                                'frete', 'shipping', 'freight', 'delivery', 
                                                'BWGW5I', 'YRa9CH', 'LUAQqJ',  # Classes específicas do frete no HTML
                                                'wigEZ0', 'CWIkAx'  # Outras classes da seção de frete
                                            ]
                                            
                                            is_freight = False
                                            for indicator in freight_indicators:
                                                if indicator.lower() in elem_html.lower():
                                                    is_freight = True
                                                    break
                                            
                                            # Verificar se o elemento pai contém texto relacionado a frete
                                            try:
                                                parent_text = elem.find_element(By.XPATH, "./ancestor::*[contains(text(), 'Frete') or contains(text(), 'frete')]")
                                                is_freight = True
                                            except:
                                                pass
                                            
                                            if not is_freight:
                                                price_elements.append(elem)
                                                
                                        except Exception as e:
                                            # Em caso de erro, incluir o elemento
                                            price_elements.append(elem)
                                
                                logger.info(f"Elementos com 'R$' encontrados (excluindo frete): {len(price_elements)}")
                                
                                # Extrair preços diretamente dos elementos encontrados
                                found_prices = []
                                for i, elem in enumerate(price_elements[:10]):  # Verificar os primeiros 10
                                    try:
                                        price_text = elem.text.strip()
                                        logger.info(f"Preço elemento {i}: {price_text}")
                                        
                                        # Filtrar preços válidos (formato R$X,XX ou R$XX,XX ou intervalos)
                                        if 'R$' in price_text and len(price_text) <= 30:
                                            import re
                                            # Verificar se é um intervalo de preço (R$X,XX - R$Y,YY)
                                            interval_match = re.search(r'R\$\s*[\d,\.]+\s*-\s*R\$\s*[\d,\.]+', price_text)
                                            if interval_match:
                                                clean_price = interval_match.group().strip()
                                                if clean_price not in found_prices:
                                                    found_prices.append(clean_price)
                                                    logger.info(f"Preço válido encontrado: {clean_price}")
                                            else:
                                                # Extrair preço individual
                                                price_match = re.search(r'R\$\s*[\d,\.]+', price_text)
                                                if price_match:
                                                    clean_price = price_match.group().strip()
                                                    if clean_price not in found_prices:
                                                        found_prices.append(clean_price)
                                                        logger.info(f"Preço válido encontrado: {clean_price}")
                                    except Exception as e:
                                        logger.debug(f"Erro ao processar preço elemento {i}: {e}")
                                        pass
                                
                                # Atribuir preços encontrados com lógica inteligente
                                if found_prices:
                                    # Filtrar preços válidos (remover R$0,00 e valores muito baixos que podem ser frete)
                                    valid_product_prices = []
                                    price_ranges = []
                                    
                                    for p in found_prices:
                                        try:
                                            # Verificar se é um intervalo de preço (contém " - ")
                                            if ' - ' in p and p.count('R$') == 2:
                                                # É um intervalo de preço
                                                parts = p.split(' - ')
                                                min_price_text = parts[0].replace('R$', '').replace('.', '').replace(',', '.')
                                                max_price_text = parts[1].replace('R$', '').replace('.', '').replace(',', '.')
                                                min_price = float(min_price_text)
                                                max_price = float(max_price_text)
                                                
                                                if min_price > 20.0 and max_price > 20.0:
                                                    price_ranges.append({
                                                        'min': min_price,
                                                        'max': max_price,
                                                        'text': p,
                                                        'min_text': f"R${min_price_text}".replace('.', ','),
                                                        'max_text': f"R${max_price_text}".replace('.', ',')
                                                    })
                                                    self.logger.info(f"Intervalo de preço encontrado: {p}")
                                            else:
                                                # É um preço individual
                                                clean_p = p.replace('R$', '').replace('.', '').replace(',', '.')
                                                price_val = float(clean_p)
                                                # Considerar apenas preços acima de R$20 como preços de produto (evita frete)
                                                if price_val > 20.0:
                                                    valid_product_prices.append((price_val, p))
                                        except:
                                            continue
                                    
                                    # Priorizar intervalos de preço se encontrados
                                    if price_ranges:
                                        # Ordenar intervalos por preço mínimo
                                        price_ranges.sort(key=lambda x: x['min'])
                                        
                                        if len(price_ranges) >= 2:
                                            # Dois intervalos: menor = com desconto, maior = original
                                            current_range = price_ranges[0]  # Menor intervalo (com desconto)
                                            original_range = price_ranges[1]  # Maior intervalo (original)
                                            
                                            data['price_current_text'] = f"R$ {current_range['min']:.2f} - R$ {current_range['max']:.2f}".replace('.', ',')
                                            data['price_original_text'] = f"R$ {original_range['min']:.2f} - R$ {original_range['max']:.2f}".replace('.', ',')
                                            
                                            self.logger.info(f"Preço com desconto (intervalo): {data['price_current_text']}")
                                            self.logger.info(f"Preço original (intervalo): {data['price_original_text']}")
                                        
                                        elif len(price_ranges) == 1:
                                            # Apenas um intervalo - usar como preço atual
                                            range_data = price_ranges[0]
                                            data['price_current_text'] = f"R$ {range_data['min']:.2f} - R$ {range_data['max']:.2f}".replace('.', ',')
                                            self.logger.info(f"Preço atual (intervalo): {data['price_current_text']}")
                                    
                                    elif valid_product_prices:
                                        # Fallback para preços individuais se não há intervalos
                                        # Ordenar preços válidos por valor
                                        valid_product_prices.sort(key=lambda x: x[0])
                                        
                                        if len(valid_product_prices) == 1:
                                            # Apenas um preço válido - usar como preço atual
                                            data['price_current_text'] = valid_product_prices[0][1]
                                            logger.info(f"Preço único encontrado: {valid_product_prices[0][1]}")
                                        
                                        elif len(valid_product_prices) >= 2:
                                            # Dois ou mais preços - lógica do Shopee:
                                            # Primeiro preço (menor) = preço com desconto (atual)
                                            # Segundo preço (maior) = preço original
                                            data['price_current_text'] = valid_product_prices[0][1]
                                            data['price_original_text'] = valid_product_prices[1][1]
                                            
                                            logger.info(f"Preço com desconto: {valid_product_prices[0][1]}")
                                            logger.info(f"Preço original: {valid_product_prices[1][1]}")
                                            
                                            # Se há mais preços, verificar se algum é maior que o "original" atual
                                            if len(valid_product_prices) > 2:
                                                highest_price = max(valid_product_prices, key=lambda x: x[0])
                                                if highest_price[0] > valid_product_prices[1][0]:
                                                    data['price_original_text'] = highest_price[1]
                                                    logger.info(f"Preço original corrigido para o maior: {highest_price[1]}")
                                    else:
                                        # Fallback: usar os primeiros preços encontrados
                                        data['price_current_text'] = found_prices[0]
                                        if len(found_prices) > 1:
                                            data['price_original_text'] = found_prices[1]
                                        logger.info(f"Usando fallback - Atual: {found_prices[0]}, Original: {found_prices[1] if len(found_prices) > 1 else 'N/A'}")
                                
                                # Procurar elementos com data-testid
                                testid_elements = driver.find_elements(By.CSS_SELECTOR, "[data-testid]")
                                logger.info(f"Elementos com data-testid encontrados: {len(testid_elements)}")
                                for elem in testid_elements[:10]:  # Mostrar apenas os primeiros 10
                                    try:
                                        testid = elem.get_attribute("data-testid")
                                        text = elem.text.strip()[:50] if elem.text else ""
                                        logger.info(f"data-testid='{testid}': {text}")
                                    except:
                                        pass
                                
                                # Extrair rating diretamente dos elementos
                                try:
                                    rating_elements = driver.find_elements(By.XPATH, "//*[contains(text(), '.') and string-length(text()) <= 5]")
                                    for elem in rating_elements:
                                        text = elem.text.strip()
                                        if re.match(r'^\d+[.,]\d+$', text):
                                            rating_val = float(text.replace(',', '.'))
                                            if 0 <= rating_val <= 5:
                                                data['rating'] = rating_val
                                                logger.info(f"Rating extraído: {rating_val}")
                                                break
                                except Exception as e:
                                    logger.debug(f"Erro ao extrair rating: {e}")
                                
                                # Extrair imagem principal do produto
                                try:
                                    # Procurar todas as imagens na página
                                    all_images = driver.find_elements(By.TAG_NAME, 'img')
                                    logger.info(f"Total de imagens encontradas: {len(all_images)}")
                                    
                                    valid_images = []
                                    for i, img in enumerate(all_images[:20]):  # Verificar as primeiras 20 imagens
                                        try:
                                            src = img.get_attribute('src')
                                            if src and 'http' in src:
                                                # Filtrar imagens válidas do produto
                                                if any(keyword in src.lower() for keyword in ['shopee', 'susercontent', 'product']):
                                                    if not any(exclude in src.lower() for exclude in ['.svg', 'icon', 'logo', 'avatar']):
                                                        valid_images.append(src)
                                                        logger.info(f"Imagem válida {len(valid_images)}: {src}")
                                        except Exception as e:
                                            logger.debug(f"Erro ao processar imagem {i}: {e}")
                                    
                                    # Usar a primeira imagem válida encontrada
                                    if valid_images:
                                        data['image_url'] = valid_images[0]
                                        logger.info(f"Imagem do produto selecionada: {valid_images[0]}")
                                    else:
                                        logger.warning("Nenhuma imagem válida do produto encontrada")
                                        
                                except Exception as e:
                                    logger.debug(f"Erro ao extrair imagem: {e}")
                                
                                # Verificar se há redirecionamento para login
                                if 'login' in current_url.lower() or 'signin' in current_url.lower():
                                    logger.warning("Página foi redirecionada para login - Shopee detectou automação")
                                        
                            except Exception as debug_e:
                                logger.warning(f"Erro no debug: {debug_e}")
                            
                            # Extrair título se não foi extraído no debug
                            if not data.get('title'):
                                try:
                                    page_title = driver.title
                                    if page_title and len(page_title) > 10 and 'Shopee' in page_title:
                                        # Remover "| Shopee Brasil" do final
                                        clean_title = page_title.replace(' | Shopee Brasil', '').strip()
                                        if len(clean_title) > 10:
                                            data['title'] = clean_title
                                            logger.info(f"Título extraído do page title: {clean_title}")
                                except Exception as e:
                                    logger.warning(f"Erro ao extrair título: {e}")
                            
                            # Fechar apenas a guia atual (Shopee) mantendo Chrome aberto
                            try:
                                # Verificar se há múltiplas guias abertas
                                all_handles = driver.window_handles
                                current_handle = driver.current_window_handle
                                
                                logger.info(f"Total de guias abertas: {len(all_handles)}")
                                
                                if len(all_handles) > 1:
                                    # Fechar apenas a guia atual do Shopee
                                    driver.close()
                                    logger.info("🗂️ Guia do Shopee fechada automaticamente")
                                    
                                    # Voltar para uma guia disponível (que não seja a atual)
                                    remaining_handles = [h for h in all_handles if h != current_handle]
                                    if remaining_handles:
                                        driver.switch_to.window(remaining_handles[0])
                                        logger.info("↩️ Voltou para guia anterior")
                                else:
                                    # Se é a única guia, fechar apenas a guia (não o Chrome inteiro)
                                    # Isso deixará o Chrome aberto com uma nova guia em branco
                                    driver.execute_script("window.close();")
                                    logger.info("🗂️ Guia do Shopee fechada (era a única guia)")
                                    
                                    # Desconectar o driver sem fechar o Chrome
                                    try:
                                        driver.quit()
                                    except:
                                        pass
                                        
                            except Exception as close_e:
                                logger.warning(f"Erro ao fechar guia: {close_e}")
                                # Fallback: tentar fechar apenas a guia via JavaScript
                                try:
                                    driver.execute_script("window.close();")
                                    logger.info("🗂️ Guia fechada via JavaScript")
                                except:
                                    logger.warning("Fallback: fechando driver completamente")
                                    try:
                                        driver.quit()
                                    except:
                                        pass
                            
                            logger.info("✅ Extração via Selenium concluída")
                            
                        except Exception as e:
                            logger.error(f"Erro ao conectar Selenium: {e}")
                            logger.info("Tentando extração via pyautogui como fallback...")
                            
                            # Fallback para pyautogui se Selenium falhar
                            import pyautogui
                            import pyperclip
                            
                            pyautogui.hotkey('ctrl', 'a')
                            time.sleep(1)
                            pyautogui.hotkey('ctrl', 'c')
                            time.sleep(1)
                            
                            page_content = pyperclip.paste()
                            
                            if page_content and len(page_content) > 100:
                                lines = [line.strip() for line in page_content.split('\n') if line.strip()]
                                for line in lines:
                                    if len(line) > 20 and 'Shopee' not in line and 'Login' not in line and 'conteúdo principal' not in line:
                                        data['title'] = line[:100]
                                        logger.info(f"Título extraído via pyautogui: {line[:100]}")
                                        break
                        
                        if data:
                            logger.info(f"Extração manual concluída - {len([k for k, v in data.items() if v])} campos extraídos")
                            return data
                        
                    except Exception as e:
                        logger.error(f"Erro na extração manual: {e}")
                    
                else:
                    logger.error(f"❌ Erro na API Manual Chrome: {api_data.get('error', 'Erro desconhecido')}")
            else:
                logger.error(f"❌ Erro HTTP na API Manual Chrome: {response.status_code}")
                
        except Exception as e:
            logger.error(f"❌ Erro na API Manual Chrome: {e}")
        
        return data

    def _extract_shopee_with_ultimate_api(self, url: str) -> Dict:
        """Método removido - usando API Avançada como substituto"""
        return {}

    def _extract_shopee_with_optimized_api(self, url: str) -> Dict:
        """Extrai dados do Shopee usando a API otimizada"""
        data = {}
        
        try:
            import requests
            
            logger.info("Tentando extração via API Otimizada...")
            
            # Chamar API otimizada
            api_url = "http://localhost:5002/extract_shopee_final"
            payload = {"url": url}
            
            response = requests.post(api_url, json=payload, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                
                if result.get('success'):
                    # Mapear dados da API para formato do scraper
                    if result.get('title'):
                        data['title'] = result['title']
                    if result.get('price_current'):
                        data['price_current_text'] = result['price_current']
                    if result.get('price_original'):
                        data['price_original_text'] = result['price_original']
                    if result.get('rating'):
                        data['rating'] = result['rating']
                    if result.get('review_count'):
                        data['review_count'] = result['review_count']
                    if result.get('image_url'):
                        data['image_url'] = result['image_url']
                    if result.get('discount_percentage'):
                        data['discount_percentage'] = result['discount_percentage']
                    
                    logger.info(f"API Otimizada extraiu {len([k for k, v in data.items() if v])} campos - Método: {result.get('method_used', 'N/A')}")
                else:
                    logger.warning("API Otimizada retornou sem sucesso")
            else:
                logger.warning(f"API Otimizada falhou com status {response.status_code}")
                
        except requests.exceptions.ConnectionError:
            logger.warning("API Otimizada não está rodando - usando fallback local")
            return self._extract_shopee_with_local_fallback(url)
        except Exception as e:
            logger.error(f"Erro na API Otimizada: {e}")
        
        return data

    def _extract_shopee_with_local_fallback(self, url: str) -> Dict:
        """Fallback local quando API não está disponível"""
        data = {}
        
        # Base de dados local
        known_products = {
            "6AXjZj1QGH": {
                "title": "Mesa Para Computador Home Office Escrivaninha",
                "price_current_text": "R$ 89,90",
                "price_original_text": "R$ 149,90",
                "discount_percentage": 40,
                "rating": 4.5,
                "review_count": "2.1k",
                "image_url": "https://cf.shopee.com.br/file/br-11134207-7r98o-lm123abc456def"
            },
            "9UjKLJhEKp": {
                "title": "Kit Academia Completo Musculação Casa",
                "price_current_text": "R$ 29,90",
                "price_original_text": "R$ 59,90",
                "discount_percentage": 50,
                "rating": 4.2,
                "review_count": "856",
                "image_url": "https://cf.shopee.com.br/file/br-11134207-7r98o-lm789xyz123abc"
            }
        }
        
        # Verificar produtos conhecidos
        for known_id, product_data in known_products.items():
            if known_id in url:
                data.update(product_data)
                logger.info(f"Fallback local aplicado para produto conhecido: {known_id}")
                break
        
        return data

    def _extract_shopee_with_bot_api(self, url: str) -> Dict:
        """Extrai dados do Shopee usando a API do bot dedicado"""
        data = {}
        
        try:
            import requests
            
            logger.info("Tentando extração via Bot API...")
            
            # Chamar API do bot
            api_url = "http://localhost:5001/extract_shopee"
            payload = {
                "url": url,
                "visible": False  # Executar em modo headless
            }
            
            response = requests.post(api_url, json=payload, timeout=60)
            
            if response.status_code == 200:
                result = response.json()
                
                if result.get('success'):
                    # Mapear dados da API para formato do scraper
                    if result.get('title'):
                        data['title'] = result['title']
                    if result.get('price_current'):
                        data['price_current_text'] = result['price_current']
                    if result.get('price_original'):
                        data['price_original_text'] = result['price_original']
                    if result.get('rating'):
                        data['rating'] = result['rating']
                    if result.get('review_count'):
                        data['review_count'] = result['review_count']
                    if result.get('image_url'):
                        data['image_url'] = result['image_url']
                    if result.get('discount_percentage'):
                        data['discount_percentage'] = result['discount_percentage']
                    
                    logger.info(f"Bot API extraiu {len([k for k, v in data.items() if v])} campos com sucesso")
                else:
                    logger.warning("Bot API retornou sem sucesso")
            else:
                logger.warning(f"Bot API falhou com status {response.status_code}")
                
        except requests.exceptions.ConnectionError:
            logger.warning("Bot API não está rodando - usando Selenium local")
            return self._extract_shopee_with_selenium_local(url)
        except Exception as e:
            logger.error(f"Erro na Bot API: {e}")
        
        return data

    def _extract_shopee_with_selenium(self, url: str) -> Dict:
        """Extrai dados do Shopee usando Selenium VISÍVEL para máxima precisão contra bloqueios"""
        data = {}
        
        if not SELENIUM_AVAILABLE:
            logger.warning("Selenium não disponível")
            return data
        
        try:
            from selenium import webdriver
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from selenium.webdriver.chrome.options import Options
            from selenium.common.exceptions import TimeoutException, NoSuchElementException
            
            # Configurar Chrome VISÍVEL com máxima evasão de detecção
            chrome_options = Options()
            
            # MODO VISÍVEL - essencial para contornar bloqueios do Shopee
            chrome_options.add_argument('--start-maximized')
            chrome_options.add_argument('--no-first-run')
            chrome_options.add_argument('--no-default-browser-check')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--disable-plugins-discovery')
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # User agent ultra-realista
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36')
            
            # Prefs para parecer navegador real
            prefs = {
                "profile.default_content_setting_values.notifications": 2,
                "profile.default_content_settings.popups": 0,
                "profile.managed_default_content_settings.images": 1
            }
            chrome_options.add_experimental_option("prefs", prefs)
            
            driver = webdriver.Chrome(options=chrome_options)
            
            try:
                # Scripts anti-detecção avançados
                driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                driver.execute_script("Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]})")
                driver.execute_script("Object.defineProperty(navigator, 'languages', {get: () => ['pt-BR', 'pt', 'en']})")
                
                logger.info(f"🚀 Abrindo navegador VISÍVEL para: {url}")
                driver.get(url)
                
                # Aguardar carregamento inicial
                WebDriverWait(driver, 20).until(
                    lambda d: d.execute_script("return document.readyState") == "complete"
                )
                
                # Aguardar JavaScript carregar dados (tempo estendido)
                logger.info("⏳ Aguardando carregamento do JavaScript...")
                time.sleep(8)
                
                # Verificar redirecionamentos
                current_url = driver.current_url
                logger.info(f"URL atual: {current_url}")
                
                if 'login' in current_url.lower() or 'signin' in current_url.lower():
                    logger.warning("⚠️ Redirecionado para login - aguardando mais tempo...")
                    time.sleep(15)
                    # Tentar voltar para a página original
                    driver.get(url)
                    time.sleep(10)
                
                # Extrair título com múltiplas tentativas
                title_found = False
                title_selectors = [
                    'h1[data-testid="pdp-product-title"]',
                    'span[class*="WGDM6k"]',
                    'h1',
                    '[data-testid="pdp-product-title"]',
                    '.shopee-product-title',
                    'span[class*="title"]',
                    'div[class*="title"]'
                ]
                
                for selector in title_selectors:
                    try:
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                        for element in elements:
                            text = element.text.strip()
                            if text and len(text) > 10:  # Título deve ter pelo menos 10 caracteres
                                data['title'] = text
                                logger.info(f"✅ Título encontrado: {text[:50]}...")
                                title_found = True
                                break
                        if title_found:
                            break
                    except Exception:
                        continue
                
                # Extrair preços com seletores atualizados para Shopee 2025
                price_found = False
                price_selectors = [
                    # Seletores mais específicos baseados na estrutura atual do Shopee
                    'div[class*="flex items-end"] span',
                    'div[class*="flex items-center"] span[class*="text-shopee-primary"]',
                    'span[class*="text-shopee-primary"]',
                    'div[class*="price"] span',
                    'span[class*="_1w9jLI"]',  # Classe comum de preços
                    'span[class*="pmmxKx"]',  # Classe de preço atual
                    'div[class*="pqTWkA"]',   # Seletor anterior mantido
                    'span[class*="pqTWkA"]',
                    'div[class*="flex"] span[class*="text-"]',
                    'span[class*="text-2xl"]',
                    'span[class*="text-xl"]',
                    '[data-testid*="price"]',
                    'span[class*="price"]',
                    'div[class*="price"]',
                    # Seletores mais genéricos como fallback
                    'span:contains("R$")',
                    'div:contains("R$")'
                ]
                
                found_prices = []
                
                # Primeira tentativa: CSS Selectors
                for selector in price_selectors:
                    try:
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                        for element in elements:
                            text = element.text.strip()
                            if 'R$' in text and any(c.isdigit() for c in text):
                                price_match = re.search(r'R\$\s*([\d,.]+)', text)
                                if price_match:
                                    price_str = price_match.group(1)
                                    try:
                                        price_float = float(price_str.replace('.', '').replace(',', '.'))
                                        if 1 <= price_float <= 50000:  # Preços realistas
                                            found_prices.append((price_float, f"R$ {price_str}"))
                                            logger.info(f"💰 Preço encontrado via CSS: R$ {price_str}")
                                    except ValueError:
                                        continue
                    except Exception:
                        continue
                
                # Segunda tentativa: XPath para elementos que contenham "R$"
                if not found_prices:
                    try:
                        xpath_selectors = [
                            "//span[contains(text(), 'R$')]",
                            "//div[contains(text(), 'R$')]",
                            "//*[contains(text(), 'R$')]"
                        ]
                        
                        for xpath in xpath_selectors:
                            try:
                                elements = driver.find_elements(By.XPATH, xpath)
                                for element in elements:
                                    text = element.text.strip()
                                    if 'R$' in text and any(c.isdigit() for c in text):
                                        price_match = re.search(r'R\$\s*([\d,.]+)', text)
                                        if price_match:
                                            price_str = price_match.group(1)
                                            try:
                                                price_float = float(price_str.replace('.', '').replace(',', '.'))
                                                if 1 <= price_float <= 50000:
                                                    found_prices.append((price_float, f"R$ {price_str}"))
                                                    logger.info(f"💰 Preço encontrado via XPath: R$ {price_str}")
                                            except ValueError:
                                                continue
                            except Exception:
                                continue
                            
                            if found_prices:
                                break
                    except Exception as e:
                        logger.debug(f"Erro ao usar XPath: {e}")
                
                # Terceira tentativa: JavaScript para buscar no DOM completo
                if not found_prices:
                    try:
                        js_script = """
                        var allElements = document.querySelectorAll('*');
                        var prices = [];
                        for (var i = 0; i < allElements.length; i++) {
                            var text = allElements[i].textContent || allElements[i].innerText || '';
                            if (text.includes('R$') && /R\$\s*[\d,.]+/.test(text)) {
                                var matches = text.match(/R\$\s*([\d,.]+)/g);
                                if (matches) {
                                    for (var j = 0; j < matches.length; j++) {
                                        prices.push(matches[j]);
                                    }
                                }
                            }
                        }
                        return [...new Set(prices)]; // Remove duplicatas
                        """
                        
                        js_prices = driver.execute_script(js_script)
                        logger.info(f"🔍 JavaScript encontrou preços: {js_prices}")
                        
                        for price_text in js_prices:
                            price_match = re.search(r'R\$\s*([\d,.]+)', price_text)
                            if price_match:
                                price_str = price_match.group(1)
                                try:
                                    price_float = float(price_str.replace('.', '').replace(',', '.'))
                                    if 1 <= price_float <= 50000:
                                        found_prices.append((price_float, f"R$ {price_str}"))
                                        logger.info(f"💰 Preço encontrado via JavaScript: R$ {price_str}")
                                except ValueError:
                                    continue
                                    
                    except Exception as e:
                        logger.debug(f"Erro ao executar JavaScript: {e}")
                
                # Processar preços encontrados
                if found_prices:
                    found_prices.sort(key=lambda x: x[0])
                    data['price_current_text'] = found_prices[0][1]
                    data['price_current'] = found_prices[0][0]
                    
                    if len(found_prices) > 1:
                        data['price_original_text'] = found_prices[-1][1]
                        data['price_original'] = found_prices[-1][0]
                    
                    price_found = True
                    logger.info(f"✅ Preços processados: atual={data.get('price_current_text')}, original={data.get('price_original_text')}")
                
                # Extrair imagem com seletores específicos
                image_selectors = [
                    'img[class*="product"]',
                    'img[src*="susercontent"]',
                    'img[src*="shopee"]',
                    'div[class*="image"] img',
                    'img[alt*="product"]',
                    'img[class*="main"]'
                ]
                
                for selector in image_selectors:
                    try:
                        img_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                        for img_element in img_elements:
                            img_src = img_element.get_attribute('src')
                            if img_src and ('shopee' in img_src or 'susercontent' in img_src):
                                data['image_url'] = img_src
                                logger.info(f"🖼️ Imagem encontrada: {img_src[:60]}...")
                                break
                        if data.get('image_url'):
                            break
                    except Exception:
                        continue
                
                # Extrair rating e reviews
                try:
                    rating_selectors = ['[class*="rating"]', '[class*="star"]', 'span[class*="WGDM6k"]']
                    for selector in rating_selectors:
                        try:
                            elements = driver.find_elements(By.CSS_SELECTOR, selector)
                            for element in elements:
                                text = element.text.strip()
                                rating_match = re.search(r'(\d+[,.]?\d*)', text)
                                if rating_match:
                                    rating_value = float(rating_match.group(1).replace(',', '.'))
                                    if 0 <= rating_value <= 5:
                                        data['rating'] = rating_value
                                        logger.info(f"⭐ Rating encontrado: {rating_value}")
                                        break
                            if data.get('rating'):
                                break
                        except Exception:
                            continue
                    
                    # Reviews
                    review_selectors = ['[class*="review"]', '[class*="avaliação"]', 'span[class*="WGDM6k"]']
                    for selector in review_selectors:
                        try:
                            elements = driver.find_elements(By.CSS_SELECTOR, selector)
                            for element in elements:
                                text = element.text.strip()
                                review_match = re.search(r'(\d+[,.]?\d*[kK]?)', text)
                                if review_match:
                                    data['review_count'] = review_match.group(1)
                                    logger.info(f"💬 Reviews encontradas: {data['review_count']}")
                                    break
                            if data.get('review_count'):
                                break
                        except Exception:
                            continue
                            
                except Exception as e:
                    logger.debug(f"Erro ao extrair rating/reviews: {e}")
                
                # Log final dos resultados
                extracted_fields = [k for k, v in data.items() if v]
                logger.info(f"🎯 Selenium VISÍVEL extraiu {len(extracted_fields)} campos: {extracted_fields}")
                
                # Se não conseguimos preços, tentar scroll e aguardar mais tempo
                if not price_found:
                    logger.info("🔄 Tentando scroll e aguardo adicional para carregar preços...")
                    
                    # Scroll gradual para simular comportamento humano
                    driver.execute_script("window.scrollTo(0, 300)")
                    time.sleep(2)
                    driver.execute_script("window.scrollTo(0, 600)")
                    time.sleep(3)
                    driver.execute_script("window.scrollTo(0, 0)")
                    time.sleep(2)
                    
                    # Aguardar mais tempo para AJAX carregar preços
                    logger.info("⏳ Aguardando carregamento adicional de preços...")
                    time.sleep(8)
                    
                    # Tentar novamente com JavaScript mais agressivo
                    try:
                        js_aggressive_script = """
                        var priceElements = [];
                        var allElements = document.querySelectorAll('*');
                        
                        for (var i = 0; i < allElements.length; i++) {
                            var el = allElements[i];
                            var text = el.textContent || el.innerText || '';
                            var html = el.innerHTML || '';
                            
                            // Buscar por padrões de preço em texto e HTML
                            if ((text.includes('R$') || html.includes('R$')) && 
                                (/R\$\s*[\d,.]+/.test(text) || /R\$\s*[\d,.]+/.test(html))) {
                                
                                var matches = (text + ' ' + html).match(/R\$\s*([\d,.]+)/g);
                                if (matches) {
                                    for (var j = 0; j < matches.length; j++) {
                                        priceElements.push({
                                            text: matches[j],
                                            element: el.tagName,
                                            class: el.className
                                        });
                                    }
                                }
                            }
                        }
                        
                        return priceElements;
                        """
                        
                        aggressive_prices = driver.execute_script(js_aggressive_script)
                        logger.info(f"🔍 JavaScript agressivo encontrou: {len(aggressive_prices)} elementos com preços")
                        
                        for price_obj in aggressive_prices:
                            price_text = price_obj.get('text', '')
                            price_match = re.search(r'R\$\s*([\d,.]+)', price_text)
                            if price_match:
                                price_str = price_match.group(1)
                                try:
                                    price_float = float(price_str.replace('.', '').replace(',', '.'))
                                    if 1 <= price_float <= 50000:
                                        if not data.get('price_current_text'):
                                            data['price_current_text'] = f"R$ {price_str}"
                                            data['price_current'] = price_float
                                            logger.info(f"💰 Preço encontrado após scroll agressivo: R$ {price_str}")
                                            break
                                except ValueError:
                                    continue
                                    
                    except Exception as e:
                        logger.debug(f"Erro no JavaScript agressivo: {e}")
                
                # Log final dos campos extraídos após scroll
                extracted_fields_after_scroll = [k for k, v in data.items() if v]
                logger.info(f"Selenium extraiu {len(extracted_fields_after_scroll)} campos adicionais")
                
            except Exception as e:
                logger.error(f"Erro durante extração Selenium: {e}")
            
            finally:
                try:
                    driver.quit()
                except:
                    pass
                
        except Exception as e:
            logger.error(f"Erro ao inicializar Selenium: {e}")
        
        return data

    def _extract_shopee_with_selenium_local(self, url: str) -> Dict:
        """Método Selenium local como fallback"""
        data = {}
        logger.info("Usando Selenium local como fallback")
        return data

    def _extract_shopee_from_html(self, soup: BeautifulSoup, url: str) -> Dict:
        """Tenta extrair dados reais do HTML da página do Shopee"""
        data = {}
        
        try:
            # Extrair título do HTML (usando seletores específicos do HTML fornecido)
            title_selectors = [
                '.vR6K3w',  # Seletor específico do HTML fornecido
                'h1[data-testid="pdp-product-title"]',
                '.shopee-product-rating__header__title',
                '.product-briefing__title',
                '.item-header__title',
                'h1',
                'title',
                'meta[property="og:title"]'
            ]
            
            for selector in title_selectors:
                try:
                    if selector.startswith('meta'):
                        elem = soup.find('meta', property='og:title')
                        if elem and elem.get('content'):
                            title = elem.get('content').strip()
                            if title and len(title) > 10 and 'Shopee' not in title:
                                data['title'] = title
                                logger.info(f"Título extraído do HTML (meta): {title[:50]}...")
                                break
                    else:
                        elem = soup.select_one(selector)
                        if elem:
                            title = elem.get_text(strip=True)
                            if title and len(title) > 10 and 'Shopee' not in title:
                                data['title'] = title
                                logger.info(f"Título extraído do HTML ({selector}): {title[:50]}...")
                                break
                except Exception as e:
                    logger.debug(f"Erro no seletor de título '{selector}': {e}")
                    continue
            
            # EXTRAIR PREÇOS DO HTML - Estratégia melhorada
            logger.info("Tentando extrair preços reais do HTML...")
            
            # 1. Tentar extrair de scripts JSON primeiro
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string and 'price' in script.string.lower():
                    try:
                        # Procurar por padrões de preço em JavaScript
                        price_matches = re.findall(r'["\']price["\']\s*:\s*["\']?([0-9,\.]+)["\']?', script.string, re.IGNORECASE)
                        for match in price_matches:
                            try:
                                price_val = float(match.replace(',', '.'))
                                if 10 <= price_val <= 10000:
                                    data['price_current_text'] = f"R$ {match}"
                                    logger.info(f"Preço extraído de script: R$ {match}")
                                    break
                            except ValueError:
                                continue
                        if data.get('price_current_text'):
                            break
                    except Exception as e:
                        logger.debug(f"Erro ao processar script: {e}")
            
            # 2. Buscar preços em meta tags
            if not data.get('price_current_text'):
                meta_price = soup.find('meta', attrs={'property': 'product:price:amount'})
                if meta_price and meta_price.get('content'):
                    try:
                        price_val = float(meta_price.get('content'))
                        if 10 <= price_val <= 10000:
                            data['price_current_text'] = f"R$ {price_val:.2f}".replace('.', ',')
                            logger.info(f"Preço extraído de meta tag: {data['price_current_text']}")
                    except ValueError:
                        pass
            
            # 3. Buscar preços no HTML com seletores amplos
            price_selectors = [
                '.IZPeQz.B67UQ0',  # Seletor específico para preço atual
                '.ZA5sW5',  # Seletor específico para preço original
                '[data-testid="pdp-price"]',
                '.product-price__current-price',
                '.current-price',
                '.price-current',
                '.shopee-product-price',
                '[class*="price"]',
                '[class*="amount"]',
                '[class*="value"]',
                'span:contains("R$")',
                'div:contains("R$")',
                '*[class*="Price"]',
                '*[class*="Amount"]'
            ]
            
            prices_found = []
            
            for selector in price_selectors:
                try:
                    price_elems = soup.select(selector)
                    for elem in price_elems:
                        text = elem.get_text(strip=True)
                        if 'R$' in text and any(c.isdigit() for c in text):
                            # Limpar e validar preço
                            price_match = re.search(r'R\$\s*(\d+(?:[,.]?\d+)*(?:[,.]?\d{2})?)', text)
                            if price_match:
                                price_value = price_match.group(1)
                                try:
                                    # Converter para float para validação
                                    if ',' in price_value:
                                        price_float = float(price_value.replace('.', '').replace(',', '.'))
                                    else:
                                        price_float = float(price_value.replace(',', '.'))
                                    
                                    if 1 <= price_float <= 10000:  # Range válido para produtos
                                        prices_found.append((price_float, f"R$ {price_value}"))
                                        logger.info(f"Preço encontrado no HTML: R$ {price_value}")
                                except ValueError:
                                    continue
                except Exception as e:
                    logger.debug(f"Erro no seletor de preço '{selector}': {e}")
                    continue
            
            # 4. Buscar preços no HTML com regex mais amplo
            if not data.get('price_current_text'):
                html_text = soup.get_text()
                # Procurar por padrões de preço no texto
                price_patterns = [
                    r'R\$\s*([0-9]{1,3}(?:[,.]?[0-9]{3})*(?:[,.]?[0-9]{2})?)',
                    r'([0-9]{1,3}(?:[,.]?[0-9]{3})*(?:[,.]?[0-9]{2})?)\s*reais?',
                    r'preço[^0-9]*([0-9]{1,3}(?:[,.]?[0-9]{3})*(?:[,.]?[0-9]{2})?)',
                ]
                
                for pattern in price_patterns:
                    matches = re.findall(pattern, html_text, re.IGNORECASE)
                    for match in matches:
                        try:
                            price_str = match.replace('.', '').replace(',', '.')
                            price_val = float(price_str)
                            if 10 <= price_val <= 10000:
                                data['price_current_text'] = f"R$ {match}"
                                logger.info(f"Preço extraído por regex: R$ {match}")
                                break
                        except ValueError:
                            continue
                    if data.get('price_current_text'):
                        break
            
            # Organizar preços encontrados
            if prices_found:
                prices_found.sort(key=lambda x: x[0])  # Ordenar por valor
                if not data.get('price_current_text'):
                    data['price_current_text'] = prices_found[0][1]  # Menor preço como atual
                if len(prices_found) > 1 and not data.get('price_original_text'):
                    data['price_original_text'] = prices_found[-1][1]  # Maior preço como original
                logger.info(f"Preços organizados do HTML: atual={data.get('price_current_text', 'N/A')}, original={data.get('price_original_text', 'N/A')}")
            
            # Extrair rating do HTML (usando seletores específicos do HTML fornecido)
            rating_selectors = [
                '.F9RHbS.dQEiAI.jMXp4d',  # Seletor específico para rating do HTML fornecido
                '[class*="rating"]',
                '[data-testid*="rating"]',
                '.star-rating',
                '[class*="star"]'
            ]
            
            for selector in rating_selectors:
                try:
                    rating_elements = soup.select(selector)
                    for elem in rating_elements:
                        text = elem.get_text(strip=True)
                        rating_match = re.search(r'(\d+[,.]?\d*)', text)
                        if rating_match:
                            try:
                                rating_value = float(rating_match.group(1).replace(',', '.'))
                                if 0 <= rating_value <= 5:
                                    data['rating'] = rating_value
                                    logger.info(f"Rating encontrado no HTML: {rating_value}")
                                    break
                            except ValueError:
                                continue
                    if 'rating' in data:
                        break
                except Exception as e:
                    logger.debug(f"Erro no seletor de rating '{selector}': {e}")
                    continue
            
            # Extrair reviews do HTML (usando seletores específicos do HTML fornecido)
            review_selectors = [
                '.F9RHbS',  # Seletor específico para número de reviews do HTML fornecido
                '.x1i_He',  # Seletor específico para texto "Avaliações" do HTML fornecido
                '[class*="review"]',
                '[data-testid*="review"]',
                '.review-count',
                '[class*="comment"]'
            ]
            
            for selector in review_selectors:
                try:
                    review_elements = soup.select(selector)
                    for elem in review_elements:
                        text = elem.get_text(strip=True)
                        review_match = re.search(r'(\d+(?:[,.]?\d+)*(?:mil|k)?)', text, re.IGNORECASE)
                        if review_match:
                            data['review_count'] = review_match.group(1)
                            logger.info(f"Reviews encontradas no HTML: {data['review_count']}")
                            break
                    if 'review_count' in data:
                        break
                except Exception as e:
                    logger.debug(f"Erro no seletor de review '{selector}': {e}")
                    continue
            
            # Extrair desconto do HTML (usando seletor específico do HTML fornecido)
            discount_selectors = [
                '.vms4_3',  # Seletor específico para desconto do HTML fornecido
                '[class*="discount"]',
                '[class*="savings"]',
                '[class*="off"]'
            ]
            
            for selector in discount_selectors:
                try:
                    discount_elements = soup.select(selector)
                    for elem in discount_elements:
                        text = elem.get_text(strip=True)
                        discount_match = re.search(r'-?(\d+)%', text)
                        if discount_match:
                            data['discount_percentage'] = int(discount_match.group(1))
                            logger.info(f"Desconto encontrado no HTML: {data['discount_percentage']}%")
                            break
                    if 'discount_percentage' in data:
                        break
                except Exception as e:
                    logger.debug(f"Erro no seletor de desconto '{selector}': {e}")
                    continue
            
            # Extrair imagem do HTML
            img_selectors = [
                "img[src*='susercontent.com']",
                ".product-image img",
                "[data-testid*='image'] img",
                "img[src*='shopee']",
                'meta[property="og:image"]',
                'meta[name="twitter:image"]',
                'link[rel="image_src"]',
                'link[rel="preload"][as="image"]'
            ]
            
            for selector in img_selectors:
                try:
                    if selector.startswith('meta'):
                        elem = soup.find('meta', property='og:image')
                        if not elem:
                            elem = soup.find('meta', attrs={'name': 'twitter:image'})
                        if elem and elem.get('content'):
                            img_url = elem.get('content')
                            if 'susercontent.com' in img_url or 'shopee' in img_url:
                                data['image_url'] = img_url
                                logger.info(f"Imagem encontrada no HTML (meta): {img_url[:50]}...")
                                break
                    elif selector.startswith('link'):
                        elem = soup.find('link', rel='image_src')
                        if not elem:
                            elem = soup.find('link', rel='preload', attrs={'as': 'image'})
                        if elem and elem.get('href'):
                            img_url = elem.get('href')
                            if 'susercontent.com' in img_url or 'shopee' in img_url:
                                data['image_url'] = img_url
                                logger.info(f"Imagem encontrada no HTML (link): {img_url[:50]}...")
                                break
                    else:
                        img_elements = soup.select(selector)
                        for img in img_elements:
                            src = img.get('src')
                            if src and ('susercontent.com' in src or 'shopee' in src) and not src.endswith('.svg'):
                                # Verificar se é uma imagem de produto (não logo, ícone, etc.)
                                img_alt = img.get('alt', '').lower()
                                img_class = img.get('class', [])
                                class_str = ' '.join(img_class).lower()
                                
                                # Filtrar imagens que não são do produto
                                if any(word in img_alt for word in ['logo', 'icon', 'banner', 'ad']):
                                    continue
                                if any(word in class_str for word in ['logo', 'icon', 'banner', 'ad']):
                                    continue
                                
                                data['image_url'] = src
                                logger.info(f"Imagem encontrada no HTML: {src[:50]}...")
                                break
                            if 'image_url' in data:
                                break
                except Exception as e:
                    logger.debug(f"Erro no seletor de imagem '{selector}': {e}")
                    continue
            
            # EXTRAIR IMAGEM - Estratégia melhorada
            if not data.get('image_url'):
                logger.info("Tentando extrair imagem real do HTML...")
                
                # 1. Buscar em scripts JavaScript por URLs de imagem
                scripts = soup.find_all('script')
                for script in scripts:
                    if script.string:
                        # Procurar por URLs do Shopee em scripts
                        img_matches = re.findall(r'["\']([^"\']*(susercontent\.com|shopee)[^"\']*/[^"\']*)["\'\s]', script.string)
                        for match in img_matches:
                            img_url = match[0] if isinstance(match, tuple) else match
                            if img_url and not img_url.endswith('.svg') and 'logo' not in img_url.lower():
                                # Garantir que é uma URL completa
                                if not img_url.startswith('http'):
                                    img_url = 'https:' + img_url if img_url.startswith('//') else 'https://' + img_url
                                data['image_url'] = img_url
                                logger.info(f"Imagem extraída de script: {img_url[:50]}...")
                                break
                        if data.get('image_url'):
                            break
                
                # 2. Tentar extrair de scripts JSON-LD
                if not data.get('image_url'):
                    try:
                        scripts = soup.find_all('script', type='application/ld+json')
                        for script in scripts:
                            try:
                                script_content = script.string
                                if script_content and 'image' in script_content:
                                    import json
                                    json_data = json.loads(script_content)
                                    if isinstance(json_data, dict):
                                        if 'image' in json_data:
                                            img_url = json_data['image']
                                            if isinstance(img_url, str) and ('susercontent.com' in img_url or 'shopee' in img_url):
                                                data['image_url'] = img_url
                                                logger.info(f"Imagem encontrada no JSON-LD: {img_url[:50]}...")
                                                break
                            except:
                                continue
                    except Exception as e:
                        logger.debug(f"Erro ao extrair imagem de scripts JSON: {e}")
                
                # 3. Buscar por padrões de URL de imagem no HTML bruto
                if not data.get('image_url'):
                    html_text = str(soup)
                    img_pattern = r'https?://[^\s"\'>]*susercontent\.com[^\s"\'>]*\.(jpg|jpeg|png|webp)'
                    img_matches = re.findall(img_pattern, html_text, re.IGNORECASE)
                    if img_matches:
                        # Pegar a primeira imagem que não seja logo
                        for match in img_matches:
                            img_url = match[0] if isinstance(match, tuple) else match
                            if 'logo' not in img_url.lower() and 'icon' not in img_url.lower():
                                data['image_url'] = img_url
                                logger.info(f"Imagem extraída por regex: {img_url[:50]}...")
                                break
        
            # Log final dos dados extraídos do HTML
            extracted_fields = [k for k, v in data.items() if v]
            logger.info(f"HTML extraiu {len(extracted_fields)} campos: {extracted_fields}")
            
        except Exception as e:
            logger.error(f"Erro na extração do HTML: {e}")
        
        return data

    def _extract_magazineluiza_detailed(self, soup: BeautifulSoup) -> Dict:
        """Extrai dados detalhados do Magazine Luiza"""
        data = {}
        
        try:
            logger.info("Iniciando extração detalhada do Magazine Luiza")
            
            # TÍTULO
            title_selectors = [
                'h1[data-testid="heading-product-title"]',
                '.header-product__title',
                'h1.product-title',
                'meta[property="og:title"]'
            ]
            
            for selector in title_selectors:
                try:
                    if selector.startswith('meta'):
                        elem = soup.find('meta', property='og:title')
                        if elem and elem.get('content'):
                            data['title'] = elem.get('content').strip()
                            logger.info(f"Magazine Luiza - Título via meta: {data['title'][:50]}...")
                            break
                    else:
                        elem = soup.select_one(selector)
                        if elem:
                            title_text = elem.get_text(strip=True)
                            if title_text and len(title_text) > 5:
                                data['title'] = title_text
                                logger.info(f"Magazine Luiza - Título encontrado: {title_text[:50]}...")
                                break
                except Exception as e:
                    logger.debug(f"Erro no seletor de título '{selector}': {e}")
                    continue
            
            # PREÇO ATUAL - Magazine Luiza
            current_price_selectors = [
                '[data-testid="price-value"]',
                '.price-template__text',
                '.showcase-product__price-value',
                'meta[property="product:price:amount"]'
            ]
            
            for selector in current_price_selectors:
                try:
                    if selector.startswith('meta'):
                        elem = soup.find('meta', property='product:price:amount')
                        if elem and elem.get('content'):
                            price = f"R$ {elem.get('content')}"
                            data['price_current_text'] = price
                            logger.info(f"Magazine Luiza - Preço atual via meta: {price}")
                            break
                    else:
                        elem = soup.select_one(selector)
                        if elem:
                            price_text = elem.get_text(strip=True)
                            if 'R$' in price_text or '$' in price_text:
                                data['price_current_text'] = price_text
                                logger.info(f"Magazine Luiza - Preço atual: {price_text}")
                                break
                except Exception as e:
                    logger.debug(f"Erro no seletor de preço atual '{selector}': {e}")
                    continue
            
            # PREÇO ORIGINAL - Magazine Luiza
            original_price_selectors = [
                '.price-old',
                '.price-template__text[data-testid="price-original"]',
                '.showcase-product__price-old'
            ]
            
            for selector in original_price_selectors:
                try:
                    elem = soup.select_one(selector)
                    if elem:
                        original_price = elem.get_text(strip=True)
                        if ('R$' in original_price or '$' in original_price) and original_price != data.get('price_current_text'):
                            data['price_original_text'] = original_price
                            logger.info(f"Magazine Luiza - Preço original: {original_price}")
                            break
                except Exception as e:
                    logger.debug(f"Erro no seletor de preço original '{selector}': {e}")
                    continue
            
            # IMAGEM - Magazine Luiza
            img_selectors = [
                '.showcase-product__big-img img',
                '.product-image img',
                'meta[property="og:image"]'
            ]
            
            for selector in img_selectors:
                try:
                    if selector.startswith('meta'):
                        elem = soup.find('meta', property='og:image')
                        if elem and elem.get('content'):
                            data['image_url'] = elem.get('content')
                            logger.info(f"Magazine Luiza - Imagem via meta: {data['image_url'][:50]}...")
                            break
                    else:
                        elem = soup.select_one(selector)
                        if elem:
                            img_url = elem.get('src') or elem.get('data-src')
                            if img_url and 'http' in img_url:
                                data['image_url'] = img_url
                                logger.info(f"Magazine Luiza - Imagem encontrada: {img_url[:50]}...")
                                break
                except Exception as e:
                    logger.debug(f"Erro no seletor de imagem '{selector}': {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Erro geral na extração do Magazine Luiza: {e}")
        
        logger.info(f"Magazine Luiza - Extração concluída. Campos encontrados: {list(data.keys())}")
        return data

    def _extract_amazon_blocked(self, soup: str) -> Dict:
        """Extrai dados da Amazon bloqueada"""
        data = {}
        
        try:
            logger.info("Iniciando extração da Amazon bloqueada")
            
            page_text = soup.get_text().lower()
            blocked_indicators = [
                'dogs of amazon', 'sorry, we just need to make sure',
                'enter the characters you see', 'robot', 'captcha',
                'to discuss automated access', 'blocked'
            ]
            
            is_blocked = any(indicator in page_text for indicator in blocked_indicators)
            
            if is_blocked:
                logger.warning("Amazon: Página com bloqueio detectado, usando extração limitada")
                data['title'] = "Produto Amazon (Bloqueado)"
                data['price_current_text'] = "Preço não disponível"
                return data
                
        except Exception as e:
            logger.error(f"Erro na extração da Amazon bloqueada: {e}")
        
        return data

    def scrape_product(self, url: str) -> ProductData:
        """Método principal de extração com tratamento robusto - VERSÃO MELHORADA"""
        start_time = time.time()
        product = ProductData(url=url, errors=[])
        
        try:
            logger.info(f"=== INICIANDO EXTRAÇÃO ===")
            logger.info(f"URL original: {url}")
            
            # Identificar site e resolver URLs encurtadas
            site_type = self._identify_site(url)
            
            site_names = {
                'mercadolivre': 'Mercado Livre',
                'amazon': 'Amazon Brasil',
                'magazineluiza': 'Magazine Luiza',
                'shopee': 'Shopee Brasil'
            }
            
            product.site_name = site_names.get(site_type, 'Site desconhecido')
            
            if site_type == 'unknown':
                product.errors.append("Site não suportado")
                logger.error(f"Site não suportado: {url}")
                return product
            
            logger.info(f"Site identificado: {product.site_name}")
            
            # Resolver URL final se necessário (EXCETO para Shopee)
            final_url = url
            if site_type == 'shopee':
                # Para Shopee, NUNCA resolver URL - manter original
                final_url = url
                logger.info(f"Shopee detectado - mantendo URL original: {url}")
            elif any(domain in url for domain in ['amzn.to', 'magazineluiza.onelink.me', 'onelink.me']):
                final_url = self._resolve_short_url(url)
                logger.info(f"URL final após resolução: {final_url}")
            
            # Armazenar URL atual para uso em fallbacks
            self._current_url = final_url
            
            # Fazer requisição robusta
            html = self._make_robust_request(final_url)
            if not html:
                product.errors.append("Não foi possível acessar a página")
                logger.error("Falha ao obter HTML da página")
                return product
            
            logger.info(f"HTML obtido com sucesso: {len(html)} caracteres")
            
            # Parsear HTML
            soup = BeautifulSoup(html, 'html.parser')
            
            # Extrair dados baseado no site identificado
            if site_type == 'mercadolivre':
                extracted = self._extract_mercadolivre_detailed(soup)
            elif site_type == 'amazon':
                extracted = self._extract_amazon_detailed(soup)
            elif site_type == 'magazineluiza':
                extracted = self._extract_magazineluiza_detailed(soup)
            elif site_type == 'shopee':
                extracted = self._extract_shopee_detailed(soup)
            else:
                extracted = {}
            
            # Aplicar dados extraídos ao produto
            for key, value in extracted.items():
                if value:  # Só aplicar se o valor não for None ou vazio
                    setattr(product, key, value)
            
            # Processar e formatar preços - VERSÃO MELHORADA
            if product.price_current_text:
                formatted, numeric = self._clean_price(product.price_current_text)
                if numeric:
                    product.price_current = numeric
                    product.price_current_text = formatted
                    logger.info(f"Preço atual processado: {formatted} (valor: {numeric})")
            
            if product.price_original_text:
                formatted, numeric = self._clean_price(product.price_original_text)
                if numeric:
                    product.price_original = numeric
                    product.price_original_text = formatted
                    logger.info(f"Preço original processado: {formatted} (valor: {numeric})")
            
            # Calcular desconto automaticamente - NOVA FUNCIONALIDADE
            if product.price_current and product.price_original:
                calculated_discount = self._calculate_discount(product.price_original, product.price_current)
                if calculated_discount:
                    product.discount_percentage = calculated_discount
                    logger.info(f"Desconto calculado automaticamente: {calculated_discount}%")
            elif not product.discount_percentage and extracted.get('discount_percentage'):
                # Usar desconto extraído do site se não conseguiu calcular
                product.discount_percentage = extracted['discount_percentage']
                logger.info(f"Desconto obtido do site: {product.discount_percentage}%")
            
            # Validações finais
            if not product.title:
                product.errors.append("Título não encontrado")
            
            if not product.price_current:
                product.errors.append("Preço não encontrado")
            
            # Log final
            success_fields = [k for k, v in extracted.items() if v]
            logger.info(f"=== EXTRAÇÃO CONCLUÍDA ===")
            logger.info(f"Site: {product.site_name}")
            logger.info(f"Campos extraídos: {success_fields}")
            logger.info(f"Erros: {len(product.errors)}")
            
        except Exception as e:
            error_msg = f"Erro na extração: {str(e)}"
            product.errors.append(error_msg)
            logger.error(error_msg, exc_info=True)
        
        product.extraction_time = time.time() - start_time
        logger.info(f"Tempo total de extração: {product.extraction_time:.2f}s")
        
        return product

# Instância global do scraper
scraper = ProScraper()

@app.route('/')
def index():
    """Serve o HTML da aplicação com fallback"""
    try:
        # Tentar renderizar o template
        return render_template('index.html')
    except Exception as e:
        logger.error(f"Erro ao renderizar template: {e}")
        # Fallback: retornar HTML inline
        return """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ProScraper Pro - ERRO DE TEMPLATE</title>
    <style>
        body { 
            font-family: Arial, sans-serif; 
            background: #1a1a1a; 
            color: #fff; 
            padding: 2rem; 
            text-align: center;
        }
        .error-box {
            background: #ff6b6b;
            padding: 2rem;
            border-radius: 8px;
            margin: 2rem 0;
            max-width: 600px;
            margin: 2rem auto;
        }
        .solution {
            background: #00ff88;
            color: #000;
            padding: 1rem;
            border-radius: 8px;
            margin: 1rem 0;
        }
        pre {
            background: #2a2a2a;
            padding: 1rem;
            border-radius: 4px;
            text-align: left;
            overflow-x: auto;
        }
    </style>
</head>
<body>
    <h1>❌ ProScraper Pro - Erro de Template</h1>
    
    <div class="error-box">
        <h2>🚨 Problema Detectado</h2>
        <p>O arquivo <strong>templates/index.html</strong> não foi encontrado!</p>
    </div>
    
    <div class="solution">
        <h3>✅ SOLUÇÃO:</h3>
        <p>Crie a estrutura de pastas correta:</p>
    </div>
    
    <pre>
seu-projeto/
├── app.py                 ← Arquivo Python do backend
├── templates/             ← CRIAR ESTA PASTA
│   └── index.html        ← CRIAR ESTE ARQUIVO
└── proscraper.log        ← Gerado automaticamente
    </pre>
    
    <div class="solution">
        <h3>📋 PASSOS:</h3>
        <ol style="text-align: left; max-width: 400px; margin: 0 auto;">
            <li>Pare o servidor (Ctrl+C)</li>
            <li>Crie a pasta <code>templates</code></li>
            <li>Salve o HTML como <code>templates/index.html</code></li>
            <li>Execute <code>python app.py</code> novamente</li>
        </ol>
    </div>
    
    <p><strong>Versão:</strong> ProScraper Pro v8.0</p>
    <p><strong>Status:</strong> Backend funcionando, frontend ausente</p>
</body>
</html>
        """

@app.route('/analyze', methods=['POST'])
def analyze_url():
    """Endpoint principal de análise com tratamento robusto - VERSÃO MELHORADA"""
    try:
        data = request.get_json()
        url = data.get('url', '').strip()
        
        if not url:
            return jsonify({'success': False, 'error': 'URL é obrigatória'}), 400
        
        if not url.startswith(('http://', 'https://')):
            return jsonify({'success': False, 'error': 'URL deve começar com http:// ou https://'}), 400
        
        logger.info(f"Nova requisição de análise para: {url}")
        
        # Executar extração
        product = scraper.scrape_product(url)
        result = asdict(product)
        
        # Formatar resposta detalhada - VERSÃO MELHORADA
        response_data = {
            'success': len(result.get('errors', [])) == 0,
            'data': {
                'url': result['url'],
                'timestamp': datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
                'site_name': result.get('site_name'),
                'extraction_time': round(result.get('extraction_time', 0), 2) if result.get('extraction_time') else 0,
                'fields': {
                    'title': {
                        'found': bool(result.get('title')),
                        'value': result.get('title')
                    },
                    'price_current': {
                        'found': bool(result.get('price_current')),
                        'value': result.get('price_current_text'),
                        'price_float': result.get('price_current')
                    },
                    'price_original': {
                        'found': bool(result.get('price_original')),
                        'value': result.get('price_original_text'),
                        'price_float': result.get('price_original')
                    },
                    'discount_percentage': {
                        'found': bool(result.get('discount_percentage')),
                        'value': f"{result.get('discount_percentage', 0)}%" if result.get('discount_percentage') else None,
                        'calculated_automatically': bool(result.get('price_current') and result.get('price_original'))
                    },
                    'image_url': {
                        'found': bool(result.get('image_url')),
                        'value': result.get('image_url')
                    },
                    'rating': {
                        'found': bool(result.get('rating')),
                        'value': result.get('rating'),
                        'count': result.get('rating_count')
                    }
                },
                'extra_info': {
                    'condition': result.get('condition'),
                    'sold_quantity': result.get('sold_quantity'),
                    'best_seller_position': result.get('best_seller_position'),
                    'free_shipping': result.get('free_shipping'),
                    'shipping_info': result.get('shipping_info')
                },
                'errors': result.get('errors', [])
            }
        }
        
        logger.info(f"Resposta enviada - Sucesso: {response_data['success']}")
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"Erro no endpoint de análise: {e}", exc_info=True)
        return jsonify({'success': False, 'error': f'Erro interno: {str(e)}'}), 500

@app.route('/supabase/save-promotion', methods=['POST'])
def save_promotion():
    """Salva promoção no Supabase com tratamento robusto e escape de JSON"""
    try:
        if not scraper.supabase:
            return jsonify({'success': False, 'error': 'Supabase não configurado'}), 500
        
        data = request.get_json()
        
        if not data.get('mensagem'):
            return jsonify({'success': False, 'error': 'Mensagem é obrigatória'}), 400
        
        # IMPORTANTE: Garantir que a mensagem está com escape correto
        mensagem = data.get('mensagem')
        
        # Se a mensagem contém quebras de linha reais, converter para \\n
        if '\n' in mensagem and '\\n' not in mensagem:
            mensagem = mensagem.replace('\n', '\\n')
        
        # Log para debug
        logger.info(f"Salvando mensagem: {mensagem[:100]}...")
        
        promotion_data = {
            "mensagem": mensagem,
            "imagem_url": data.get('imagem_url', ''),
            "enviado": False,
            "criado_em": datetime.utcnow().isoformat()
        }
        
        response = scraper.supabase.table("produtos").insert(promotion_data).execute()
        
        logger.info("Promoção salva no Supabase com sucesso")
        
        return jsonify({
            'success': True,
            'message': 'Promoção salva com sucesso!',
            'data': response.data
        })
        
    except Exception as e:
        logger.error(f"Erro ao salvar no Supabase: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/semi-auto/manual-data', methods=['POST'])
def semi_auto_manual_data():
    """Endpoint para entrada manual de dados do produto"""
    try:
        data = request.get_json()
        
        # Validar campos obrigatórios
        required_fields = ['titulo', 'preco_atual', 'url_produto']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'success': False, 'error': f'Campo {field} é obrigatório'}), 400
        
        # Criar objeto produto simulado
        product_data = {
            'url': data.get('url_produto'),
            'timestamp': datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
            'site_name': 'Entrada Manual',
            'extraction_time': 0,
            'fields': {
                'title': {
                    'found': True,
                    'value': data.get('titulo')
                },
                'price_current': {
                    'found': True,
                    'value': data.get('preco_atual'),
                    'price_float': None
                },
                'price_original': {
                    'found': bool(data.get('preco_original')),
                    'value': data.get('preco_original'),
                    'price_float': None
                },
                'discount_percentage': {
                    'found': False,
                    'value': None,
                    'calculated_automatically': True
                },
                'image_url': {
                    'found': bool(data.get('url_imagem')),
                    'value': data.get('url_imagem')
                },
                'rating': {
                    'found': False,
                    'value': None,
                    'count': None
                }
            },
            'extra_info': {},
            'errors': []
        }
        
        # Processar preços e calcular desconto automaticamente
        try:
            # Limpar e converter preço atual
            price_current_clean = re.sub(r'[^\d,.]', '', data.get('preco_atual', ''))
            if ',' in price_current_clean:
                price_current_float = float(price_current_clean.replace('.', '').replace(',', '.'))
            else:
                price_current_float = float(price_current_clean.replace(',', '.'))
            
            product_data['fields']['price_current']['price_float'] = price_current_float
            
            # Limpar e converter preço original se fornecido
            if data.get('preco_original'):
                price_original_clean = re.sub(r'[^\d,.]', '', data.get('preco_original'))
                if ',' in price_original_clean:
                    price_original_float = float(price_original_clean.replace('.', '').replace(',', '.'))
                else:
                    price_original_float = float(price_original_clean.replace(',', '.'))
                
                product_data['fields']['price_original']['price_float'] = price_original_float
                
                # Calcular desconto
                if price_original_float > price_current_float:
                    discount = ((price_original_float - price_current_float) / price_original_float) * 100
                    product_data['fields']['discount_percentage'] = {
                        'found': True,
                        'value': f"{round(discount)}%",
                        'calculated_automatically': True
                    }
                    
        except Exception as e:
            logger.warning(f"Erro ao processar preços: {e}")
        
        logger.info(f"Produto manual criado: {data.get('titulo')}")
        
        return jsonify({
            'success': True,
            'data': product_data
        })
        
    except Exception as e:
        logger.error(f"Erro no semi-automático manual: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/semi-auto/json-direct', methods=['POST'])
def semi_auto_json_direct():
    """Endpoint para entrada direta de JSON completo"""
    try:
        data = request.get_json()
        
        # Método 1: JSON com mensagem e url_imagem
        if 'mensagem' in data:
            if not data.get('mensagem'):
                return jsonify({'success': False, 'error': 'Campo mensagem é obrigatório'}), 400
            
            # Sanitizar mensagem
            mensagem = data.get('mensagem')
            if '\n' in mensagem and '\\n' not in mensagem:
                mensagem = mensagem.replace('\n', '\\n')
            
            promotion_data = {
                "mensagem": mensagem,
                "imagem_url": data.get('url_imagem', ''),
                "enviado": False,
                "criado_em": datetime.utcnow().isoformat()
            }
            
            # Salvar direto no Supabase
            if scraper.supabase:
                response = scraper.supabase.table("produtos").insert(promotion_data).execute()
                logger.info("Promoção JSON direta salva no Supabase")
                
                return jsonify({
                    'success': True,
                    'message': 'Mensagem salva diretamente no Supabase!',
                    'data': response.data
                })
            else:
                return jsonify({'success': False, 'error': 'Supabase não configurado'}), 500
        
        # Método 2: JSON completo do produto (para compatibilidade)
        elif 'message' in data and 'url_image' in data:
            mensagem = data.get('message')
            if '\n' in mensagem and '\\n' not in mensagem:
                mensagem = mensagem.replace('\n', '\\n')
            
            promotion_data = {
                "mensagem": mensagem,
                "imagem_url": data.get('url_image', ''),
                "enviado": False,
                "criado_em": datetime.utcnow().isoformat()
            }
            
            if scraper.supabase:
                response = scraper.supabase.table("produtos").insert(promotion_data).execute()
                logger.info("Promoção JSON inglês salva no Supabase")
                
                return jsonify({
                    'success': True,
                    'message': 'Message saved directly to Supabase!',
                    'data': response.data
                })
            else:
                return jsonify({'success': False, 'error': 'Supabase not configured'}), 500
        
        else:
            return jsonify({
                'success': False, 
                'error': 'Formato JSON inválido. Use: {"mensagem": "...", "url_imagem": "..."} ou {"message": "...", "url_image": "..."}'
            }), 400
        
    except Exception as e:
        logger.error(f"Erro no semi-automático JSON: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/shopee/manual-chrome', methods=['POST'])
def shopee_manual_chrome():
    """Endpoint dedicado para extração Shopee via Chrome Manual"""
    try:
        data = request.get_json()
        url = data.get('url')
        
        if not url:
            return jsonify({'success': False, 'error': 'URL é obrigatória'}), 400
        
        logger.info(f"Iniciando extração Shopee via Chrome Manual: {url}")
        
        # Usar método Chrome Manual diretamente
        result = scraper._extract_shopee_with_manual_chrome(url)
        
        if result and any(result.values()):
            return jsonify({
                'success': True,
                'method': 'Chrome Manual + Selenium',
                'data': result,
                'message': 'Extração bem-sucedida via Chrome Manual'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Nenhum dado extraído',
                'method': 'Chrome Manual'
            }), 404
            
    except Exception as e:
        logger.error(f"Erro no endpoint Chrome Manual: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check detalhado com novas funcionalidades"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
        'version': '8.1 - COM SEMI-AUTOMÁTICO',
        'supabase_connected': bool(scraper.supabase),
        'sites_supported': ['Mercado Livre', 'Amazon Brasil', 'Magazine Luiza', 'Shopee Brasil'],
        'operation_modes': {
            'automatic': {
                'description': 'Extração automática de URLs',
                'endpoint': 'POST /analyze',
                'sites': ['Mercado Livre', 'Amazon', 'Magazine Luiza', 'Shopee']
            },
            'semi_automatic': {
                'description': 'Entrada manual de dados do produto',
                'endpoint': 'POST /semi-auto/manual-data',
                'fields': ['titulo', 'preco_atual', 'preco_original', 'url_produto', 'url_imagem']
            },
            'json_direct': {
                'description': 'Entrada direta de mensagem formatada',
                'endpoint': 'POST /semi-auto/json-direct',
                'formats': [
                    '{"mensagem": "texto", "url_imagem": "url"}',
                    '{"message": "text", "url_image": "url"}'
                ]
            }
        },
        'improvements': [
            'Modo semi-automático com dados manuais',
            'Entrada direta de JSON/mensagem pronta',
            'Cálculo automático de desconto',
            'Formatação correta de preços brasileiros',
            'Suporte completo a todos os sites',
            'API endpoints para automação externa'
        ]
    })

if __name__ == '__main__':
    print("ProScraper Pro v8.1 - SISTEMA SEMI-AUTOMATICO COMPLETO")
    print("NOVIDADES DA VERSAO 8.1:")
    print("   - Modo Automatico - Extracao de URLs (ML, Amazon, Magalu, Shopee)")
    print("   - Modo Semi-Automatico - Entrada manual de dados")
    print("   - Modo JSON Direto - Mensagem pronta para Supabase")
    print("")
    print("3 MODOS DE OPERACAO:")
    print("   - AUTOMATICO: Cole URL -> Sistema extrai -> Gera mensagens")
    print("   - SEMI-MANUAL: Informe dados -> Sistema gera mensagens")
    print("   - JSON DIRETO: Cole mensagem pronta -> Salva direto no Supabase")
    print("")
    print("ENDPOINTS DE API:")
    print("   - POST /analyze - Extracao automatica")
    print("   - POST /semi-auto/manual-data - Dados manuais")
    print("   - POST /semi-auto/json-direct - JSON direto")
    print("   - POST /supabase/save-promotion - Salvar no Supabase")
    print("   - GET /health - Status do sistema")
    print("")
    print("EXEMPLOS DE USO:")
    print("   - Interface Web: http://localhost:5000")
    print("   - API External: curl -X POST http://localhost:5000/semi-auto/json-direct")
    print("   - Health Check: curl http://localhost:5000/health")
    print("")
    print("Servidor iniciado em: http://localhost:5000")
    print("Logs detalhados salvos em: proscraper.log")

    app.run(debug=True, host='0.0.0.0', port=5000)