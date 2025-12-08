import streamlit as st
import pandas as pd
import time
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.os_manager import ChromeType
from bs4 import BeautifulSoup
from io import BytesIO

# === 1. 爬蟲驅動設定 (雲端專用版) ===
def get_driver():
    chrome_options = Options()
    # 關鍵：雲端主機沒有螢幕，必須開啟 headless (無頭模式)
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # 自動判斷環境安裝 Chrome
    try:
        # 優先嘗試安裝 Chromium (適合 Streamlit Cloud Linux 環境)
        service = Service(ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
    except:
        # 備用：嘗試安裝一般 Chrome (適合本地測試)
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
    return driver

# === 2. 爬蟲核心邏輯 ===
def run_momo_spider(brand_name, max_pages):
    driver = get_driver()
    all_products = []
    seen_ids = set()
    
    status_text = st.empty() 
    progress_bar = st.progress(0)

    try:
        for page in range(1, max_pages + 1):
            status_text.text(f"⏳ 正在抓取第 {page} / {max_pages} 頁，請稍候...")
            progress_bar.progress(int((page / max_pages) * 100))
            
            url = f"https://www.momoshop.com.tw/search/searchShop.jsp?keyword={brand_name}&searchType=1&curPage={page}&_isFuzzy=0&showType=chessboardType"
            driver.get(url)
            time.sleep(1)
            
            # 滾動頁面
            for i in range(5):
                driver.execute_script("window.scrollBy(0, 1000);")
                time.sleep(0.5)
            
            soup = BeautifulSoup(driver.page_source, "html.parser")
            links = soup.select("a[href*='GoodsDetail.jsp']")
            
            for link in links:
                try:
                    href = link.get('href', '')
                    if href.startswith('/'):
                        full_url = "https://www.momoshop.com.tw" + href
                    else:
                        full_url = href

                    id_match = re.search(r'i_code=(\d+)', href)
                    if not id_match: continue
                    i_code = id_match.group(1)

                    if i_code in seen_ids: continue
                    seen_ids.add(i_code)

                    product_name = ""
                    if not product_name: product_name = link.get('title', '').strip()
                    if not product_name:
                        img_tag = link.select_one('img')
                        if img_tag: product_name = img_tag.get('alt', '').strip() or img_tag.get('title', '').strip()
                    if not product_name:
                        title_tag = link.select_one('.prdName') or link.select_one('.goodsName')
                        if title_tag: product_name = title_tag.text.strip()

                    if not product_name: continue

                    model_match = re.search(r'([A-Z]{2,}-\w+)', product_name, re.IGNORECASE)
                    model_number = model_match.group(1) if model_match else ""

                    price = "0"
                    sales = "0"
                    
                    container = link.find_parent('li')
                    if container:
                        price_tag = container.select_one('.price') or container.select_one('.money') or container.select_one('b')
                        if price_tag: price = re.sub(r'[^\d]', '', price_tag.text)
                        
                        sales_tag = container.select_one('.totalSales')
                        if sales_tag: sales = sales_tag.text.replace('總銷量', '').replace('>', '').strip()
                    
                    all_products.append({
                        "品牌名稱": brand_name,
                        "產品名稱": product_name,
                        "產品型號": model_number,
                        "價格": price,
                        "產品銷量": sales,
                        "商品連結": full_url
                    })

                except Exception:
                    continue
            
            time.sleep(1)

    except Exception as e:
        st.error(f"發生錯誤: {e}")
    finally:
        driver.quit()
        status_text.text("✅ 抓取完成！")
        progress_bar.progress(100)
        
    return all_products

# === 3. 網頁介面設計 ===
st.set_page_config(page_title="Momo 品牌爬蟲", page_icon="🛒")
st.title("🛒 Momo 品牌商品爬蟲")
st.markdown("輸入品牌，自動抓取價格與銷量，並下載 Excel 表格。")

with st.sidebar:
    st.header("⚙️ 設定")
    brand_input = st.text_input("輸入品牌名稱", value="輝葉")
    pages_input = st.slider("抓取頁數", 1, 10, 2)
    st.info("雲端版請耐心等待，速度會比本機稍慢。")
    start_btn = st.button("🚀 開始抓取", type="primary")

st.divider()

if start_btn:
    if not brand_input:
        st.warning("請輸入品牌名稱！")
    else:
        with st.spinner('正在啟動雲端爬蟲...請稍候 (約需 20-40 秒)'):
            data = run_momo_spider(brand_input, pages_input)
        
        if data:
            df = pd.DataFrame(data)
            cols = ["品牌名稱", "產品名稱", "產品型號", "價格", "產品銷量", "商品連結"]
            df = df[cols]
            
            st.success(f"成功！共抓取 {len(df)} 筆資料。")
            st.dataframe(df)
            
            # Excel 下載
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)
            excel_data = output.getvalue()
            
            st.download_button(
                label="📥 點擊下載 Excel 檔案",
                data=excel_data,
                file_name=f"{brand_input}_Momo_{timestamp}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )
        else:
            st.error("未抓到資料。")