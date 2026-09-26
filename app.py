import json
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

这套规则适用于任何游戏类型（贪吃蛇、俄罗斯方块、打砖块、飞机、接水果等），不是某一款游戏的特例。

【生命周期——必须遵守】
1. 页面脚本一旦运行，游戏必须立刻进入可玩状态。不要再做「开始游戏」按钮或开局遮罩（外层容器会统一提供开始/重开）。
2. 失败或胜利时，必须弹出覆盖游戏区的结束遮罩，包含：大字「游戏结束」、结果说明、得分（如果该游戏有分数）、超大按钮「再来一局」。
3. 点「再来一局」必须先把所有状态重置为初始值，再启动游戏循环。不能出现必须立刻按键才继续、或重置后立刻判负的情况。
4. 暂停只是进行中的附加功能，不能代替开始/结束界面。

【输入与可读性】
5. 只输出完整 HTML（含 CSS、JS），不要解释，不要 markdown 代码块。
6. 用中文写标题和操作说明。方向键控制时必须 event.preventDefault()。
7. 禁止把 Tab 当作游戏按键；即使用户要求 Tab，也改成上方向键或空格，并在说明里写明。
8. 角色、方块、蛇身、子弹等必须高对比鲜艳，禁止深色画在深色背景上。
9. canvas 设置 tabindex="0"，加载和点击时让 canvas 获得焦点。
10. 开局给玩家反应时间，不要生成后立刻死亡。
11. 深色现代化页面，画布居中，禁止滚动条，内容自适应屏幕。
"""

FOCUS_SCRIPT = """
<script>
(function () {
  function focusPlayArea() {
    try { window.focus(); } catch (e) {}
    var canvas = document.querySelector("canvas");
    if (canvas) {
      if (!canvas.hasAttribute("tabindex")) canvas.setAttribute("tabindex", "0");
      canvas.style.outline = "none";
      try { canvas.focus(); } catch (e) {}
    } else if (document.body) {
      document.body.setAttribute("tabindex", "0");
      try { document.body.focus(); } catch (e) {}
    }
  }
  window.addEventListener("load", focusPlayArea);
  document.addEventListener("pointerdown", focusPlayArea, true);
  document.addEventListener("keydown", function (e) {
    if (["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Space"].indexOf(e.code) !== -1) {
      e.preventDefault();
    }
  }, true);
})();
</script>
"""

GAME_SHELL = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>游戏</title>
  <style>
    html, body {
      margin: 0;
      height: 100%;
      overflow: hidden;
      background: #0b1020;
      color: #e8eefc;
      font-family: system-ui, sans-serif;
    }
    #atoms-game-shell {
      height: 100%;
      display: flex;
      flex-direction: column;
    }
    #atoms-toolbar {
      flex: 0 0 auto;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 10px 16px;
      background: #121a2e;
      border-bottom: 1px solid #2a3658;
      font-size: 14px;
      line-height: 1.5;
    }
    #atoms-toolbar button {
      cursor: pointer;
      border: 0;
      border-radius: 10px;
      padding: 8px 16px;
      font-size: 14px;
      font-weight: 700;
      color: #082016;
      background: linear-gradient(90deg, #5eead4, #67e8f9);
      white-space: nowrap;
    }
    #atoms-toolbar button:disabled {
      opacity: 0.4;
      cursor: not-allowed;
    }
    #atoms-stage {
      flex: 1;
      position: relative;
      min-height: 0;
    }
    #atoms-frame {
      width: 100%;
      height: 100%;
      border: 0;
      display: none;
      background: #0b1020;
    }
    #atoms-overlay {
      position: absolute;
      inset: 0;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 16px;
      background: radial-gradient(circle at top, #1e293b, #0b1020 70%);
    }
    #atoms-overlay h1 { margin: 0; font-size: 28px; }
    #atoms-overlay p {
      margin: 0 24px;
      opacity: 0.85;
      text-align: center;
      max-width: 520px;
      line-height: 1.6;
    }
    #atoms-start {
      cursor: pointer;
      border: 0;
      border-radius: 14px;
      padding: 16px 36px;
      font-size: 20px;
      font-weight: 800;
      color: #062016;
      background: linear-gradient(90deg, #34d399, #22d3ee);
      box-shadow: 0 10px 30px rgba(34, 211, 238, 0.25);
    }
  </style>
</head>
<body>
  <div id="atoms-game-shell">
    <div id="atoms-toolbar">
      <div>所有游戏同一流程：点「点击开始游戏」才运行 · 结束后点游戏里的「再来一局」，或点右上角「重新开始」整局重载。</div>
      <button type="button" id="atoms-restart" disabled>重新开始</button>
    </div>
    <div id="atoms-stage">
      <div id="atoms-overlay">
        <h1 id="atoms-title"></h1>
        <p>先点下方按钮开始。方向键生效前请再点一下游戏画面。失败/胜利后会出现结束提示。</p>
        <button type="button" id="atoms-start">点击开始游戏</button>
      </div>
      <iframe id="atoms-frame" title="game"></iframe>
    </div>
  </div>
  <script>
    const GAME_HTML = __GAME_HTML__;
    const GAME_TITLE = __GAME_TITLE__;
    const overlay = document.getElementById("atoms-overlay");
    const frame = document.getElementById("atoms-frame");
    const startBtn = document.getElementById("atoms-start");
    const restartBtn = document.getElementById("atoms-restart");
    document.getElementById("atoms-title").textContent = GAME_TITLE || "准备开始";

    function focusGame() {
      try { frame.contentWindow.focus(); } catch (e) {}
      try {
        const doc = frame.contentDocument;
        if (!doc) return;
        const canvas = doc.querySelector("canvas");
        if (canvas) {
          canvas.setAttribute("tabindex", "0");
          canvas.style.outline = "none";
          canvas.focus();
        } else if (doc.body) {
          doc.body.setAttribute("tabindex", "0");
          doc.body.focus();
        }
      } catch (e) {}
    }

    function loadGame() {
      overlay.style.display = "none";
      frame.style.display = "block";
      restartBtn.disabled = false;
      frame.onload = focusGame;
      frame.srcdoc = GAME_HTML;
      // 兼容处理：srcdoc 在某些浏览器不触发 onload，延迟手动调用一次
      setTimeout(focusGame, 300);
    }

    startBtn.addEventListener("click", loadGame);
    restartBtn.addEventListener("click", loadGame);
    frame.addEventListener("pointerdown", focusGame);
  </script>
</body>
</html>
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


def extract_game_title(html_code: str) -> str:
    match = re.search(r"<h1[^>]*>(.*?)</h1>", html_code, re.I | re.S)
    if not match:
        match = re.search(r"<title[^>]*>(.*?)</title>", html_code, re.I | re.S)
    if not match:
        return "准备开始"
    title = re.sub(r"<[^>]+>", "", match.group(1))
    title = re.sub(r"\s+", " ", title).strip()
    return title[:40] or "准备开始"


def inject_focus_script(html_code: str) -> str:
    if "focusPlayArea" in html_code:
        return html_code
    if "</body>" in html_code:
        return html_code.replace("</body>", FOCUS_SCRIPT + "</body>", 1)
    return html_code + FOCUS_SCRIPT


def wrap_game_html(html_code: str) -> str:
    html_code = clean_generated_html(html_code)
    if 'id="atoms-game-shell"' in html_code:
        return html_code
    inner = inject_focus_script(html_code)
    # 用 json.dumps 进行安全转义，避免出现裸露的 \n 和 \uXXXX
    inner_json = json.dumps(inner)
    title_json = json.dumps(extract_game_title(inner))
    return (
        GAME_SHELL.replace("__GAME_HTML__", inner_json)
        .replace("__GAME_TITLE__", title_json)
    )


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
    st.info(
        "所有生成的游戏都走同一套流程：先点「点击开始游戏」；"
        "玩的时候点一下画面再用方向键；失败/胜利后点「再来一局」，或点右上角「重新开始」。"
    )
    st.components.v1.html(wrap_game_html(st.session_state.play_html), height=860, scrolling=False)
else:
    st.caption("生成游戏后会显示在这里。也可以从左侧历史记录打开以前的游戏。")
