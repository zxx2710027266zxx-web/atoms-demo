import re
import sqlite3
import datetime
import streamlit as st
from openai import OpenAI

# ================= 配置区 =================
API_KEY = "sk-fiviqzaqpiddwjijtxjtpphdhhggxvpgyorgwinedaeqrxfq"  # 换成你自己的硅基流动 API Key
BASE_URL = "https://api.siliconflow.cn/v1"
MODEL_NAME = "deepseek-ai/DeepSeek-V3"

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

SYSTEM_PROMPT = """你是一个资深的前端游戏开发工程师。请根据用户需求生成一个完整、能直接运行的 HTML5 游戏。

要求：
1. 只输出完整 HTML（含 CSS 和 JS），不要解释，不要 markdown 代码块标记。
2. 页面顶部必须显示游戏标题，以及清晰的操作说明（例如“按方向键控制移动”）。
3. 游戏必须能响应键盘事件（方向键等），在键盘事件处理函数里调用 event.preventDefault()，防止页面滚动。
4. 游戏开始前或结束时，必须有清晰的提示文字（如“按任意方向键开始”“游戏结束，按 R 键重新开始”）。
5. 游戏结束后，必须重置所有状态再重新开始，不能出现“重开后必须立刻按键才能继续”的情况。
6. 开局给玩家反应时间，不要一生成就立刻死亡。
7. 深色现代化页面，画布居中，禁止出现滚动条，内容自适应屏幕。
8. 角色、方块、蛇身、子弹等必须高对比鲜艳，禁止深色画在深色背景上。
9. canvas 设置 tabindex="0"，加载和点击时让 canvas 获得焦点。
10. 禁止把 Tab 当作游戏按键。
"""


def init_db():
    conn = sqlite3.connect("history.db")
    c = conn.cursor()
    c.execute(
        """CREATE TABLE IF NOT EXISTS history
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  prompt TEXT,
                  html TEXT,
                  timestamp TEXT)"""
    )
    conn.commit()
    conn.close()


def clean_generated_html(html_code: str) -> str:
    html_code = (html_code or "").replace("```html", "").replace("```", "").strip()
    return html_code


def save_history(prompt: str, html_code: str):
    conn = sqlite3.connect("history.db")
    c = conn.cursor()
    c.execute(
        "INSERT INTO history (prompt, html, timestamp) VALUES (?, ?, ?)",
        (prompt, html_code, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    )
    conn.commit()
    conn.close()


def load_history_rows():
    conn = sqlite3.connect("history.db")
    c = conn.cursor()
    c.execute("SELECT id, prompt, timestamp FROM history ORDER BY id DESC LIMIT 10")
    rows = c.fetchall()
    conn.close()
    return rows


def load_html_by_id(record_id: int):
    conn = sqlite3.connect("history.db")
    c = conn.cursor()
    c.execute("SELECT html FROM history WHERE id = ?", (record_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None


init_db()

st.set_page_config(page_title="Atoms Demo", layout="wide")
st.title("🧱 Atoms Demo - AI 游戏生成器")

if "play_html" not in st.session_state:
    st.session_state.play_html = None

with st.sidebar:
    st.header("📜 历史记录")
    rows = load_history_rows()
    if not rows:
        st.write("暂无历史记录")
    else:
        st.caption("点击记录可重新打开游戏")
        for row in rows:
            label = f"🕒 {row[2]} - {row[1]}"
            if st.button(label, key=f"hist_{row[0]}"):
                html = load_html_by_id(row[0])
                if html:
                    st.session_state.play_html = clean_generated_html(html)

prompt = st.text_input("请输入你想要生成的游戏描述：", "做一个简单的贪吃蛇游戏")

if st.button("✨ 生成游戏"):
    if not prompt:
        st.warning("请先输入游戏描述！")
    else:
        with st.spinner("AI 正在生成代码，请稍候..."):
            try:
                response = client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.7,
                )
                html_code = clean_generated_html(response.choices[0].message.content)
                save_history(prompt, html_code)
                st.session_state.play_html = html_code
                st.success("生成成功！")
            except Exception as e:
                st.error(f"生成失败，请检查 API Key 或网络。报错信息：{e}")

if st.session_state.play_html:
    st.components.v1.html(st.session_state.play_html, height=800, scrolling=False)
else:
    st.caption("生成游戏后会显示在这里。也可以从左侧历史记录打开以前的游戏。")