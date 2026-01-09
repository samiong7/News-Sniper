import streamlit as st
import yfinance as yf
import pandas as pd
import feedparser
import requests
import time
from datetime import datetime
from deep_translator import GoogleTranslator

# ==========================================
# 🔐 إعدادات تيليجرام الآمنة (من الخزنة السرية)
# ==========================================
try:
    TELEGRAM_TOKEN = st.secrets["TELEGRAM_TOKEN"]
    TELEGRAM_CHANNEL_ID = st.secrets["TELEGRAM_CHANNEL_ID"]
except:
    # قيم فارغة في حال عدم وجود الخزنة لتجنب توقف الموقع
    TELEGRAM_TOKEN = ""
    TELEGRAM_CHANNEL_ID = ""

# دالة إرسال الرسالة (مختصرة لرؤوس الأقلام)
def send_telegram_msg(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHANNEL_ID: return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    params = {"chat_id": TELEGRAM_CHANNEL_ID, "text": message, "parse_mode": "Markdown", "disable_web_page_preview": True}
    try:
        requests.get(url, params=params, timeout=5)
    except: pass
# ==========================================

# 1. إعدادات الصفحة
st.set_page_config(page_title="News Live FX 💎", layout="wide")
st.title("News Live FX 💎 - غرفة الأخبار الحصرية")

# --- تهيئة الذاكرة ---
if 'sent_news_ids' not in st.session_state:
    st.session_state['sent_news_ids'] = []

# --- القائمة الجانبية ---
with st.sidebar:
    st.header("⚙️ الإعدادات")
    st.caption("نسخة النخبة: Bloomberg & Reuters Only")
    
    auto_refresh = st.checkbox("⏰ تحديث تلقائي (دقيقة)", value=True)
    sound_alert = st.checkbox("🔔 تنبيه صوتي", value=True)
    telegram_on = st.checkbox("✈️ إرسال للقناة الآلية", value=False)
    
    if st.button("🔄 تحديث البيانات"):
        st.rerun()
    
    # حالة الاتصال
    if telegram_on:
        if TELEGRAM_TOKEN:
            st.success(f"متصل بالقناة: {TELEGRAM_CHANNEL_ID}")
        else:
            st.error("خطأ: التوكن غير موجود في Secrets!")

# 2. الأصول (تم تعديل البحث ليكون دقيقاً)
assets_config = {
    "EUR/USD": {"symbol": "EURUSD=X", "query": "EURUSD"},
    "GBP/USD": {"symbol": "GBPUSD=X", "query": "GBPUSD"},
    "Gold (XAU)": {"symbol": "GC=F", "query": "Gold price"},
    "Oil (WTI)": {"symbol": "CL=F", "query": "Crude Oil price"},
    "Bitcoin": {"symbol": "BTC-USD", "query": "Bitcoin crypto"},
    "US Markets": {"symbol": "^DJI", "query": "Stock Market US Economy"} # Dow Jones
}

# 3. دوال مساعدة
def get_translation(text):
    try:
        return GoogleTranslator(source='auto', target='ar').translate(text)
    except:
        return text

def fetch_premium_news(query):
    # الفلتر القوي: نضيف site:bloomberg.com OR site:reuters.com للبحث مباشرة
    search_q = f"{query} (site:bloomberg.com OR site:reuters.com)"
    url = f"https://news.google.com/rss/search?q={search_q}+when:6h&hl=en-US&gl=US&ceid=US:en"
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
        df = ticker.history(period="1d", interval="15m") # فاصل أكبر قليلاً للسرعة
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

# الخطوة 2: الأخبار الحصرية + البث
news_bar = st.progress(0, text="جاري البحث في رويترز وبلومبيرج...")
idx = 0
new_news_found = False

for name, info in assets_config.items():
    feed = fetch_premium_news(info['query'])
    
    if feed and len(feed.entries) > 0:
        for entry in feed.entries[:2]: # نأخذ أحدث خبرين فقط
            
            # فلتر إضافي للتأكد 100%
            source = entry.source.title if hasattr(entry, 'source') else ""
            is_bloomberg = "Bloomberg" in source
            is_reuters = "Reuters" in source
            
            if not (is_bloomberg or is_reuters):
                continue # تخطي أي خبر ليس منهما

            # التجهيز
            badge = "🟦" if is_bloomberg else "🟧"
            current_price = prices_cache.get(name, "---")
            is_new = entry.title not in st.session_state['sent_news_ids']

            if is_new:
                new_news_found = True
            
            # --- الإرسال لتيليجرام (نمط رؤوس أقلام) ---
            if telegram_on and is_new:
                # نتحقق من التوكن
                if TELEGRAM_TOKEN:
                    ar_title = get_translation(entry.title)
                    
                    # الرسالة المختصرة
                    msg_body = (
                        f"{badge} *{source}*\n"
                        f"🔻 {ar_title}\n"
                    )
                    
                    send_telegram_msg(msg_body)
                    st.session_state['sent_news_ids'].append(entry.title)
                    
                    # تنظيف الذاكرة
                    if len(st.session_state['sent_news_ids']) > 100:
                        st.session_state['sent_news_ids'].pop(0)

            # --- التجهيز للعرض في الجدول ---
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
                "السعر": current_price,
                "المصدر": f"{badge} {source}",
                "الخبر": ar_title_display
            })
    
    idx += 1
    news_bar.progress(int((idx / len(assets_config)) * 100))

news_bar.empty()

# الصوت
if sound_alert and new_news_found:
    st.toast("خبر حصري جديد!", icon="💎")
    st.markdown("""<audio autoplay><source src="https://assets.mixkit.co/active_storage/sfx/2869/2869-preview.mp3" type="audio/mpeg"></audio>""", unsafe_allow_html=True)

# العرض النهائي
if all_data:
    df = pd.DataFrame(all_data).sort_values(by="time_obj", ascending=False)
    st.dataframe(
        df.drop(columns=["time_obj"]),
        column_config={
            "الأصل": st.column_config.TextColumn("الأصل", width="small"),
            "السعر": st.column_config.TextColumn("السعر", width="small"),
            "الخبر": st.column_config.TextColumn("العنوان", width="large"),
            "المصدر": st.column_config.TextColumn("المصدر", width="medium"),
        },
        use_container_width=True,
        hide_index=True
    )
else:
    st.info("لا توجد أخبار حديثة من بلومبيرج أو رويترز في الساعات الماضية.")

if auto_refresh:
    time.sleep(60)
    st.rerun()
