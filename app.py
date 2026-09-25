import streamlit as st
from openai import OpenAI
import sqlite3
import datetime

# ================= 配置区 =================
API_KEY = "sk-fiviqzaqpiddwjijtxjtpphdhhggxvpgyorgwinedaeqrxfq"  # 换成你自己的硅基流动 API Key
BASE_URL = "https://api.siliconflow.cn/v1"
MODEL_NAME = "deepseek-ai/DeepSeek-V3"

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

def init_db():
    conn = sqlite3.connect('history.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS history
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  prompt TEXT,
                  html TEXT,
                  timestamp TEXT)''')
    conn.commit()
    conn.close()

init_db()

st.set_page_config(page_title="Atoms Demo", layout="wide")
st.title("🧱 Atoms Demo - AI 游戏生成器")

with st.sidebar:
    st.header("📜 历史记录")
    conn = sqlite3.connect('history.db')
    c = conn.cursor()
    c.execute("SELECT prompt, timestamp FROM history ORDER BY id DESC LIMIT 10")
    rows = c.fetchall()
    conn.close()
    if not rows:
        st.write("暂无历史记录")
    else:
        for row in rows:
            st.caption(f"🕒 {row[1]} - {row[0]}")

prompt = st.text_input("请输入你想要生成的游戏描述：", "做一个简单的贪吃蛇游戏")

if st.button("✨ 生成游戏"):
    if not prompt:
        st.warning("请先输入游戏描述！")
    else:
        with st.spinner('AI 正在生成代码，请稍候...'):
            try:
                response = client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=[
                        {"role": "system", "content": "你是一个资深的前端游戏开发工程师。请根据用户的需求，生成一个完整的、能直接运行的HTML5游戏。要求：1. 必须包含完整的HTML、CSS和JavaScript代码；2. 游戏必须能响应键盘事件（比如方向键）；3. 必须有游戏结束和重新开始的逻辑；4. 重新开始时，必须先将所有游戏状态（蛇的位置、方向、分数、游戏结束标志）重置为初始状态，再启动游戏循环；5. 游戏开局时，蛇不能立即判定撞墙或撞到自己，必须给玩家一个反应时间；6. 只输出HTML代码，不要输出任何解释性文字，不要使用markdown代码块标记。"},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7
                )
                html_code = response.choices[0].message.content
                # 过滤掉 markdown 代码块标记
                html_code = html_code.replace("```html", "").replace("```", "").strip()
                conn = sqlite3.connect('history.db')
                c = conn.cursor()
                c.execute("INSERT INTO history (prompt, html, timestamp) VALUES (?, ?, ?)",
                          (prompt, html_code, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                conn.commit()
                conn.close()
                st.success("生成成功！")
                st.components.v1.html(html_code, height=600, scrolling=True)
            except Exception as e:
                st.error(f"生成失败，请检查 API Key 或网络。报错信息：{e}")