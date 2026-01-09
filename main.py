import streamlit as st
import yfinance as yf
import pandas as pd
import feedparser
import requests
import time
from datetime import datetime
from deep_translator import GoogleTranslator

# ==========================================
# 🔐 إعدادات تيليجرام الآمنة (يقرأ من Secrets)
# ==========================================
# محاولة جلب البيانات من الخزنة السرية، وإذا لم توجد نتركها فارغة لتجنب الخطأ
try:
    TELEGRAM_TOKEN = st.secrets["TELEGRAM_TOKEN"]
    TELEGRAM_CHANNEL_ID = st.secrets["TELEGRAM_CHANNEL_ID"]
except:
    TELEGRAM_TOKEN = ""
    TELEGRAM_CHANNEL_ID = ""

# دالة إرسال الرسالة
def send_telegram_msg(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHANNEL_ID: return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    params = {"chat_id": TELEGRAM_CHANNEL_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.get(url, params=params)
    except: pass
# ==========================================

# 1. إعدادات الصفحة
st.set_page_config(page_title="News Sniper 📡", layout="wide")
st.title("News Sniper 📡 - غرفة البث المباشر")

# --- تهيئة الذاكرة ---
if 'last_vip_news' not in st.session_state:
    st.session_state['last_vip_news'] = []
if 'sent_news_ids' not in st.session_state:
    st.session_state['sent_news_ids'] = []

# --- القائمة الجانبية ---
with st.sidebar:
    st.header("⚙️ الإعدادات")
    auto_refresh = st.checkbox("⏰ تحديث تلقائي", value=True)
    sound_alert = st.checkbox("🔔 تنبيه صوتي (VIP)", value=True)
    telegram_on = st.checkbox("✈️ إرسال للقناة الآلية", value=False)
    vip_only = st.checkbox("⭐ مصادر VIP فقط", value=False)
    
    if st.button("🔄 تحديث البيانات"):
        st.rerun()
    
    # رسالة حالة الاتصال بتيليجرام
    if telegram_on:
        if TELEGRAM_TOKEN:
            st.success(f"متصل بالقناة: {TELEGRAM_CHANNEL_ID}")
        else:
            st.error("خطأ: لم يتم العثور على التوكن في Secrets!")

# 2. الأصول
assets_config = {
    "EUR/USD": {"symbol": "EURUSD=X", "query": "EURUSD forex trading"},
    "GBP/USD": {"symbol": "GBPUSD=X", "query": "GBPUSD currency"},
    "Gold (XAU)": {"symbol": "GC=F", "query": "Gold price commodity"},
    "Oil (WTI)": {"symbol": "CL=F", "query": "Crude Oil WTI price"},
    "Bitcoin": {"symbol": "BTC-USD", "query": "Bitcoin crypto currency"},
    "Dow Jones": {"symbol": "YM=F", "query": "Dow Jones Industrial Average"},
    "Nasdaq": {"symbol": "NQ=F", "query": "Nasdaq 100 stock market"}
}

# 3. دوال مساعدة
def get_translation(text):
    try:
        time.sleep(0.1)
        return GoogleTranslator(source='auto', target='ar').translate(text)
    except:
        return text

def fetch_news_safe(query):
    url = f"https://news.google.com/rss/search?q={query}+when:12h&hl=en-US&gl=US&ceid=US:en"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            return feedparser.parse(response.content)
    except: pass
    return None

# --- المحرك الرئيسي ---
all_data = []
prices_cache = {}

# الخطوة 1: الأسعار
price_bar = st.progress(0, text="جاري تحديث الأسعار...")
idx = 0
for name, info in assets_config.items():
    try:
        ticker = yf.Ticker(info['symbol'])
        df = ticker.history(period="1d", interval="5m")
        if not df.empty:
            curr = df['Close'].iloc[-1]
            change = ((curr - df['Open'].iloc[0]) / df['Open'].iloc[0]) * 100
            trend = "🟢" if change >= 0 else "🔴"
            prices_cache[name] = f"{curr:,.2f} {trend}"
        else:
            prices_cache[name] = "---"
    except:
        prices_cache[name] = "---"
    idx += 1
    price_bar.progress(int((idx / len(assets_config)) * 100))
price_bar.empty()

# الخطوة 2: الأخبار + البث
news_bar = st.progress(0, text="جاري جلب الأخبار...")
idx = 0
new_vip_found = False

for name, info in assets_config.items():
    feed = fetch_news_safe(info['query'])
    
    if feed and len(feed.entries) > 0:
        for entry in feed.entries[:2]:
            source = entry.source.title if hasattr(entry, 'source') else "Unknown"
            is_vip = any(x in source for x in ["Bloomberg", "Reuters", "CNBC", "Financial", "Yahoo", "Investing"])
            
            if vip_only and not is_vip: continue

            vip_badge = "⭐ VIP" if is_vip else ""
            current_price = prices_cache.get(name, "---")
            is_new_news = entry.title not in st.session_state['sent_news_ids']

            if is_vip and is_new_news:
                new_vip_found = True
            
            # --- منطق الإرسال لتيليجرام ---
            if telegram_on and is_new_news:
                # نتحقق من وجود التوكن أولاً
                if TELEGRAM_TOKEN:
                    ar_title_tg = get_translation(entry.title)
                    msg_body = (
                        f"🚨 *{vip_badge} خبر جديد: {name}*\n\n"
                        f"📰 {ar_title_tg}\n\n"
                        f"💰 السعر الحالي: {current_price}\n"
                        f"📢 المصدر: {source}"
                    )
                    send_telegram_msg(msg_body)
                    st.session_state['sent_news_ids'].append(entry.title)
                    if len(st.session_state['sent_news_ids']) > 100:
                        st.session_state['sent_news_ids'].pop(0)

            # تجهيز العرض
            ar_title_display = get_translation(entry.title)
            if hasattr(entry, 'published_parsed'):
                pub_time = datetime(*entry.published_parsed[:6]).strftime("%H:%M")
                sort_time = datetime(*entry.published_parsed[:6])
            else:
                pub_time = "--:--"
                sort_time = datetime.now()

            all_data.append({
                "time_obj": sort_time,
                "التوقيت": pub_time,
                "الأصل": name,
                "السعر (Live)": current_price,
                "المصدر": f"{vip_badge} {source}",
                "الخبر (مترجم)": ar_title_display
            })
    
    idx += 1
    news_bar.progress(int((idx / len(assets_config)) * 100))

news_bar.empty()

# الصوت
if sound_alert and new_vip_found:
    st.markdown("""<audio autoplay><source src="https://assets.mixkit.co/active_storage/sfx/2869/2869-preview.mp3" type="audio/mpeg"></audio>""", unsafe_allow_html=True)
    st.toast("خبر جديد وصل!", icon="🔔")

# العرض
if all_data:
    df = pd.DataFrame(all_data).sort_values(by="time_obj", ascending=False)
    st.dataframe(
        df.drop(columns=["time_obj"]),
        column_config={
            "الأصل": st.column_config.TextColumn("الأصل", width="small"),
            "السعر (Live)": st.column_config.TextColumn("السعر", width="small"),
            "الخبر (مترجم)": st.column_config.TextColumn("العنوان", width="large"),
            "المصدر": st.column_config.TextColumn("المصدر", width="medium"),
        },
        use_container_width=True,
        hide_index=True
    )
else:
    st.warning("جاري البحث...")

if auto_refresh:
    time.sleep(60)
    st.rerun()
