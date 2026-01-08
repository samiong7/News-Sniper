import streamlit as st
import yfinance as yf
import pandas as pd
import feedparser
import requests
import time
from datetime import datetime
from deep_translator import GoogleTranslator

# 1. إعدادات الصفحة
st.set_page_config(page_title="News Sniper 🏆", layout="wide")
st.title("News Sniper 🏆 - غرفة القيادة المركزية")

# --- تهيئة الذاكرة (Session State) للتنبيهات ---
if 'last_vip_news' not in st.session_state:
    st.session_state['last_vip_news'] = []

# --- القائمة الجانبية (لوحة التحكم) ---
with st.sidebar:
    st.header("⚙️ إعدادات الغرفة")
    
    # خيارات التحكم
    auto_refresh = st.checkbox("⏰ تحديث تلقائي (كل 60 ثانية)", value=True)
    sound_alert = st.checkbox("🔔 تنبيه صوتي (للأخبار الهامة)", value=True)
    vip_only = st.checkbox("⭐ تصفية VIP فقط (Bloomberg/Reuters)", value=False)
    debug_mode = st.checkbox("🛠️ وضع فحص الأخطاء (Debug)", value=False)
    
    st.divider()
    if st.button("🔄 تحديث يدوي الآن"):
        st.rerun()

    st.info("💡 يتم تحليل الأثر الاقتصادي وترجمة العناوين آلياً")

# 2. إعداد الأصول (عقود آجلة وفوركس)
assets_config = {
    "EUR/USD": {"symbol": "EURUSD=X", "query": "EURUSD forex trading"},
    "GBP/USD": {"symbol": "GBPUSD=X", "query": "GBPUSD currency"},
    "Gold (XAU)": {"symbol": "GC=F", "query": "Gold price commodity market"},
    "Oil (WTI)": {"symbol": "CL=F", "query": "Crude Oil WTI price"},
    "Bitcoin": {"symbol": "BTC-USD", "query": "Bitcoin crypto currency"},
    "Dow Jones": {"symbol": "YM=F", "query": "Dow Jones Industrial Average"},
    "Nasdaq": {"symbol": "NQ=F", "query": "Nasdaq 100 stock market"}
}

# 3. الدوال المساعدة (القلب النابض للبرنامج)

# أ. دالة الترجمة
def get_translation(text):
    try:
        return GoogleTranslator(source='auto', target='ar').translate(text)
    except Exception as e:
        return text # في حال فشل الترجمة نعيد النص الأصلي

# ب. دالة التحليل الذكي (النسخة المصححة)
def analyze_impact(text, asset_name):
    text = text.lower()
    asset = asset_name.lower()
    
    # 1. التضخم والفائدة (قواعد عكسية)
    # ارتفاع التضخم/الفائدة = سيء للأسهم والذهب، جيد للدولار
    if any(w in text for w in ["inflation", "cpi", "rate hike", "interest rate", "fed", "policy"]):
        if any(w in text for w in ["rise", "high", "jump", "soar", "up", "hike"]):
            return "🟢 إيجابي (قوة للدولار)" if "usd" in asset else "🔴 سلبي (ضغط تضخم/فائدة)"
        if any(w in text for w in ["drop", "fall", "low", "cut", "down", "cool"]):
            return "🔴 سلبي (ضعف للدولار)" if "usd" in asset else "🟢 إيجابي (انتعاش)"

    # 2. البطالة والركود
    if any(w in text for w in ["unemployment", "jobless", "recession", "claims"]):
        if any(w in text for w in ["rise", "high", "jump", "up"]):
            return "🔴 سلبي (مخاوف ركود)"
        if any(w in text for w in ["drop", "fall", "low", "down"]):
            return "🟢 إيجابي (قوة اقتصادية)"

    # 3. الجيوسياسية (حروب)
    # الحرب = جيد للذهب والنفط، سيء للباقي
    if any(w in text for w in ["war", "conflict", "tension", "attack", "crisis", "geopolitical", "military"]):
        if any(w in asset for w in ["gold", "oil", "xau", "wti"]):
            return "🟢 إيجابي (ملاذ آمن/نقص إمداد)"
        else:
            return "🔴 سلبي (خوف وتوتر)"

    # 4. القواعد العامة (حركة السعر المباشرة)
    if any(w in text for w in ["rise", "jump", "surge", "gain", "high", "soar", "rally", "bull", "record"]):
        return "🟢 إيجابي (صعود)"
        
    if any(w in text for w in ["drop", "fall", "crash", "loss", "low", "bear", "plunge", "sink", "slump"]):
        return "🔴 سلبي (هبوط)"

    return "🟡 محايد / للمراقبة"

# ج. دالة جلب الأخبار (مع تخطي حظر جوجل)
def fetch_news_safe(query):
    url = f"https://news.google.com/rss/search?q={query}+when:12h&hl=en-US&gl=US&ceid=US:en"
    # هوية متصفح مزيفة
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            return feedparser.parse(response.content)
        elif debug_mode:
            st.error(f"خطأ اتصال بالمصدر: {response.status_code}")
    except Exception as e:
        if debug_mode: st.error(f"فشل الاتصال: {e}")
    return None

# 4. المحرك الرئيسي (تجميع البيانات)
all_data = []
new_vip_found = False # علم لتشغيل الجرس

# شريط تقدم
progress_text = "جاري مسح الأسواق، الترجمة، وتحليل الاتجاه..."
my_bar = st.progress(0, text=progress_text)
step = 0

for name, info in assets_config.items():
    price_display = "---"
    
    # A. السعر المباشر
    try:
        ticker = yf.Ticker(info['symbol'])
        # فاصل 5 دقائق أكثر استقراراً للبيانات المجانية
        df = ticker.history(period="1d", interval="5m")
        if not df.empty:
            curr = df['Close'].iloc[-1]
            change = ((curr - df['Open'].iloc[0]) / df['Open'].iloc[0]) * 100
            trend_icon = "🟢" if change >= 0 else "🔴"
            price_display = f"{curr:,.2f} {trend_icon}"
    except: pass

    # B. الأخبار والترجمة
    feed = fetch_news_safe(info['query'])
    if feed and len(feed.entries) > 0:
        # نأخذ أول خبرين فقط
        for entry in feed.entries[:2]:
            # التحقق من المصدر VIP
            source = entry.source.title if hasattr(entry, 'source') else "Unknown"
            is_vip = any(x in source for x in ["Bloomberg", "Reuters", "CNBC", "Financial", "Yahoo", "Investing"])
            
            # فلتر VIP
            if vip_only and not is_vip:
                continue

            vip_badge = "⭐ VIP" if is_vip else ""
            
            # تنبيه صوتي للأخبار الجديدة
            if is_vip and entry.title not in st.session_state['last_vip_news']:
                new_vip_found = True
                st.session_state['last_vip_news'].append(entry.title)
                if len(st.session_state['last_vip_news']) > 20:
                    st.session_state['last_vip_news'].pop(0)

            # التجهيز للجدول
            if hasattr(entry, 'published_parsed'):
                pub_time = datetime(*entry.published_parsed[:6]).strftime("%H:%M")
                sort_time = datetime(*entry.published_parsed[:6])
            else:
                pub_time = "--:--"
                sort_time = datetime.now()

            # *** هنا يكمن السحر: الترجمة والتحليل الذكي ***
            translated_title = get_translation(entry.title)
            impact_analysis = analyze_impact(entry.title, name) # نرسل اسم الأصل للدالة

            all_data.append({
                "time_obj": sort_time,
                "التوقيت": pub_time,
                "الأصل المتأثر": name,
                "السعر الحالي": price_display,
                "المصدر": f"{vip_badge} {source}",
                "الخبر (العربية)": translated_title,
                "تحليل الاتجاه": impact_analysis
            })
    
    step += 1
    my_bar.progress(int((step / len(assets_config)) * 100), text=progress_text)

my_bar.empty()

# 5. تشغيل التنبيه الصوتي (Sound Alert)
if sound_alert and new_vip_found:
    sound_html = """
    <audio autoplay>
    <source src="https://assets.mixkit.co/active_storage/sfx/2869/2869-preview.mp3" type="audio/mpeg">
    </audio>
    """
    st.markdown(sound_html, unsafe_allow_html=True)
    st.toast("🚨 خبر VIP جديد وصل للتو!", icon="🔔")

# 6. عرض الجدول النهائي
if all_data:
    df = pd.DataFrame(all_data).sort_values(by="time_obj", ascending=False)
    
    st.dataframe(
        df.drop(columns=["time_obj"]), # إخفاء عمود الترتيب
        column_config={
            "الأصل المتأثر": st.column_config.TextColumn("الأصل", width="small"),
            "الخبر (العربية)": st.column_config.TextColumn("عنوان الخبر (مترجم)", width="large"),
            "تحليل الاتجاه": st.column_config.TextColumn("الأثر المتوقع", width="medium"),
            "المصدر": st.column_config.TextColumn("المصدر", width="medium"),
        },
        use_container_width=True,
        hide_index=True
    )
else:
    st.warning("جاري البحث... أو لا توجد أخبار تطابق الفلاتر الحالية.")

# 7. التحديث التلقائي (Auto Refresh)
if auto_refresh:
    time.sleep(60)
    st.rerun()