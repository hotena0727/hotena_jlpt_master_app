# ============================================================
# ✅ 하테나 문법 퀴즈(뜻 맞히기) - A안 완성판 (복붙용 단일 파일)
# - 레벨: N5~N1
# - 문제: 문법(일본어)을 보고 한국어 뜻 고르기(4지선다)
# - 로그인/회원가입(Supabase Auth) + 쿠키 세션 복원
# - 홈/퀴즈/마이페이지/관리자 라우팅
# - 오답노트 + 오답만 다시풀기
# - “맞힌 문법 제외 초기화” (유형은 1개라 레벨별로만 관리)
# - 사운드 토글 + 테스트 재생 + 제출 후 1회 SFX
# - ✅ 오답(보기) 설계 개선 + tag 자동 생성(없으면 추정)
# ============================================================

from pathlib import Path
import random
import pandas as pd
import streamlit as st
import unicodedata
from supabase import create_client
from streamlit_cookies_manager import EncryptedCookieManager
import streamlit.components.v1 as components
from collections import Counter
import time
import traceback
import base64
import re
import html
import textwrap
import streamlit.components.v1 as components

# ============================================================
# ✅ Page Config
# ============================================================
st.set_page_config(page_title="Grammar Quiz", layout="centered")

# ============================================================
# ✅ 문법 태그(기능) 자동 추정(룰 기반)  ← (중요) load_pool보다 위에 있어야 함
# - CSV에 tag 컬럼이 없어도 자동 생성해서 사용 가능
# - 목적 태그로 'に$' 같은 과도 규칙은 제거(쏠림 방지)
# ============================================================
def guess_grammar_tag(grammar: str) -> str:
    g = unicodedata.normalize("NFKC", str(grammar or "")).strip()

    rules = [
        ("양보/역접", [r"のに$", r"くせに$", r"ながら(も)?$", r"とはいえ$", r"にもかかわらず$", r"それでも", r"それなのに"]),
        ("조건/가정", [r"ば$", r"たら$", r"なら$", r"と$", r"かぎり", r"限り", r"うちは", r"あいだ", r"間"]),
        ("원인/이유", [r"ので$", r"から$", r"ため(に)?$", r"せいで$", r"おかげで"]),
        ("목적", [r"ために$", r"ように$", r"に向けて", r"にむけて"]),
        ("추측/전달/간접", [r"そうだ$", r"らしい$", r"ようだ$", r"みたい$", r"とのこと", r"という"]),
        ("의무/금지", [r"なければならない$", r"なくてはいけない$", r"てはならない$", r"てはいけない$", r"ちゃだめ"]),
        ("능력/가능", [r"ことができる$", r"られる$", r"れる$"]),
        ("희망/의지", [r"たい$", r"つもり$", r"ようと思う", r"うと思う", r"ことにする$"]),
        ("경험/완료/상태", [r"たことがある$", r"てしまう$", r"てある$", r"ておく$", r"ている$"]),
        ("사역", [r"させる$", r"させられる$"]),
        ("수량/정도", [r"くらい", r"ぐらい", r"ほど", r"ばかり", r"だらけ", r"しか", r"だけ"]),
        ("시간/순서", [r"前に$", r"後で$", r"あとで$", r"間に$", r"うちに$", r"ところ", r"最中"]),
        ("열거/추가", [r"し$", r"だけでなく", r"のみならず", r"ほか", r"以外"]),
        ("기본", [r".*"]),
    ]

    for tag, patterns in rules:
        for p in patterns:
            if re.search(p, g):
                return tag
    return "기본"

# ============================================================
# ✅ [SOUND] 사운드 유틸 (모바일 자동재생 정책 대응)
# ============================================================
def _audio_autoplay_data_uri(mime: str, b: bytes):
    b64 = base64.b64encode(b).decode("utf-8")
    st.markdown(
        f"""
        <audio autoplay>
          <source src="data:{mime};base64,{b64}">
        </audio>
        """,
        unsafe_allow_html=True,
    )

def play_sound_file(path: str):
    """assets/*.mp3 or *.wav"""
    try:
        p = (BASE_DIR / path).resolve() if not str(path).startswith("/") else Path(path)
        if not p.exists():
            if is_admin():
                st.warning(f"[SOUND] 파일 없음: {p}")
            return
        data = p.read_bytes()
        mime = "audio/mpeg" if str(p).lower().endswith(".mp3") else "audio/wav"
        _audio_autoplay_data_uri(mime, data)
    except Exception as e:
        if is_admin():
            st.error("[SOUND] 재생 실패")
            st.exception(e)

def render_sound_toggle():
    if "sound_enabled" not in st.session_state:
        st.session_state.sound_enabled = False

    c1, c2, c3 = st.columns([1.4, 4.6, 4.0], vertical_alignment="center")
    with c1:
        st.session_state.sound_enabled = st.toggle(
            "🔊", value=st.session_state.sound_enabled, label_visibility="collapsed"
        )
    with c2:
        st.caption("소리 " + ("ON ✅" if st.session_state.sound_enabled else "OFF"))
    with c3:
        if st.session_state.sound_enabled:
            if st.button("🔈 테스트", use_container_width=True, key="btn_sound_test"):
                play_sound_file("assets/correct.mp3")

def sfx(event: str):
    if not st.session_state.get("sound_enabled", False):
        return
    mp = {
        "correct": "assets/correct.mp3",
        "wrong":   "assets/wrong.mp3",
        "perfect": "assets/perfect.mp3",
    }
    path = mp.get(event)
    if path:
        play_sound_file(path)

# ============================================================
# ✅ Fonts + CSS
# ============================================================
st.markdown(
    """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Kosugi+Maru&family=Noto+Sans+JP:wght@400;500;700;800&display=swap" rel="stylesheet">

<style>
:root{ --jp-rounded: "Noto Sans JP","Kosugi Maru","Hiragino Sans","Yu Gothic","Meiryo",sans-serif; }
.jp, .jp *{ font-family: var(--jp-rounded) !important; line-height:1.7; letter-spacing:.2px; }

div[data-testid="stRadio"] * ,
div[data-baseweb="radio"] * ,
label[data-baseweb="radio"] * {
  font-family: var(--jp-rounded) !important;
}

/* 헤더 여백 */
div[data-testid="stMarkdownContainer"] h2,
div[data-testid="stMarkdownContainer"] h3,
div[data-testid="stMarkdownContainer"] h4{
  margin-top: 10px !important;
  margin-bottom: 8px !important;
}

/* 버튼 기본 */
div.stButton > button {
  padding: 6px 10px !important;
  font-size: 13px !important;
  line-height: 1.1 !important;
  white-space: nowrap !important;
}

/* 상단 환영바 */
.headbar{
  display:flex;
  align-items:flex-end;
  justify-content:space-between;
  gap:12px;
  margin: 10px 0 16px 0;
}
.headtitle{
  font-size:34px;
  font-weight:900;
  line-height:1.15;
  white-space: nowrap;
}
.headhello{
  font-size: 13px;
  font-weight:700;
  opacity:.88;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 52%;
}
.headhello .mail{
  font-weight:600;
  opacity:.75;
  margin-left:8px;
}
@media (max-width: 480px){
  div[data-baseweb="button-group"] button{
    padding: 9px 12px !important;
    font-size: 14px !important;
  }
  .headhello .mail{ display:none !important; }
  .headhello{ font-size:11px; }
  .headtitle{ font-size:24px; }
}

/* ====== 레벨 버튼 카드 스타일 ====== */
.qtypewrap div.stButton > button{
  height: 46px !important;
  border-radius: 14px !important;
  font-weight: 900 !important;
  font-size: 14px !important;
  border: 1px solid rgba(120,120,120,0.22) !important;
  background: rgba(255,255,255,0.04) !important;
  box-shadow: none !important;
  transition: transform .08s ease, box-shadow .08s ease, filter .08s ease;
}
.qtypewrap div.stButton > button:hover{
  transform: translateY(-1px);
  box-shadow: 0 12px 26px rgba(0,0,0,0.12) !important;
  filter: brightness(1.02);
}

/* 캡션(안내) */
.qtype_hint{
  font-size: 15px;
  opacity: .70;
  margin-top: 2px;
  margin-bottom: 10px;
  line-height: 1.2;
}

/* divider 간격 */
.tight-divider hr{
  margin: 6px 0 10px 0 !important;
}

/* Q번호(subheader) 아래 간격만 줄이기 */
div[data-testid="stMarkdownContainer"] h3{
  margin-bottom: 4px !important;
}
</style>
""",
    unsafe_allow_html=True,
)

# ============================================================
# ✅ Scroll Top Anchor + Helpers
# ============================================================
st.markdown('<div id="__TOP__"></div>', unsafe_allow_html=True)

def scroll_to_top(nonce: int = 0):
    components.html(
        f"""
        <script>
        (function () {{
          const doc = window.parent.document;
          const targets = [
            doc.querySelector('[data-testid="stAppViewContainer"]'),
            doc.querySelector('[data-testid="stMain"]'),
            doc.querySelector('section.main'),
            doc.documentElement,
            doc.body
          ].filter(Boolean);

          const go = () => {{
            try {{
              const top = doc.getElementById("__TOP__");
              if (top) top.scrollIntoView({{behavior: "auto", block: "start"}});
              targets.forEach(t => {{
                if (t && typeof t.scrollTo === "function") t.scrollTo({{top: 0, left: 0, behavior: "auto"}});
                if (t) t.scrollTop = 0;
              }});
              window.parent.scrollTo(0, 0);
              window.scrollTo(0, 0);
            }} catch(e) {{}}
          }};

          go();
          requestAnimationFrame(go);
          setTimeout(go, 50);
          setTimeout(go, 150);
          setTimeout(go, 350);
          setTimeout(go, 800);
        }})();
        </script>
        <!-- nonce:{nonce} -->
        """,
        height=1,
    )

def render_floating_scroll_top():
    components.html(
        """
<script>
(function(){
  const doc = window.parent.document;
  if (doc.getElementById("__FAB_TOP__")) return;

  const btn = doc.createElement("button");
  btn.id = "__FAB_TOP__";
  btn.textContent = "↑";

  btn.style.position = "fixed";
  btn.style.right = "14px";
  btn.style.zIndex = "2147483647";
  btn.style.width = "46px";
  btn.style.height = "46px";
  btn.style.borderRadius = "999px";
  btn.style.border = "1px solid rgba(120,120,120,0.25)";
  btn.style.background = "rgba(0,0,0,0.55)";
  btn.style.color = "#fff";
  btn.style.fontSize = "18px";
  btn.style.fontWeight = "900";
  btn.style.boxShadow = "0 10px 22px rgba(0,0,0,0.25)";
  btn.style.cursor = "pointer";
  btn.style.userSelect = "none";
  btn.style.display = "flex";
  btn.style.alignItems = "center";
  btn.style.justifyContent = "center";
  btn.style.opacity = "0";

  const applyDeviceVisibility = () => {
    try {
      const w = window.parent.innerWidth || window.innerWidth;
      if (w >= 801) btn.style.display = "none";
      else btn.style.display = "flex";
    } catch(e) {}
  };

  const goTop = () => {
    try {
      const top = doc.getElementById("__TOP__");
      if (top) top.scrollIntoView({behavior:"smooth", block:"start"});

      const targets = [
        doc.querySelector('[data-testid="stAppViewContainer"]'),
        doc.querySelector('[data-testid="stMain"]'),
        doc.querySelector('section.main'),
        doc.documentElement,
        doc.body
      ].filter(Boolean);

      targets.forEach(t => {
        if (t && typeof t.scrollTo === "function") t.scrollTo({top:0, left:0, behavior:"smooth"});
        if (t) t.scrollTop = 0;
      });

      window.parent.scrollTo(0,0);
      window.scrollTo(0,0);
    } catch(e) {}
  };

  btn.addEventListener("click", goTop);

  const mount = () => doc.querySelector('[data-testid="stAppViewContainer"]') || doc.body;

  const BASE = 18;
  const EXTRA = 34;

  const reposition = () => {
    try {
      const vv = window.parent.visualViewport || window.visualViewport;
      const innerH = window.parent.innerHeight || window.innerHeight;
      const hiddenBottom = vv ? Math.max(0, innerH - vv.height - (vv.offsetTop || 0)) : 0;
      btn.style.bottom = (BASE + EXTRA + hiddenBottom) + "px";
      btn.style.opacity = "1";
    } catch(e) {
      btn.style.bottom = "220px";
      btn.style.opacity = "1";
    }
    applyDeviceVisibility();
  };

  const tryAttach = (n=0) => {
    const root = mount();
    if (!root) {
      if (n < 30) return setTimeout(() => tryAttach(n+1), 50);
      return;
    }
    root.appendChild(btn);
    reposition();
    setTimeout(reposition, 50);
    setTimeout(reposition, 200);
    setTimeout(reposition, 600);
  };

  tryAttach();
  window.parent.addEventListener("resize", reposition, {passive:true});

  const vv = window.parent.visualViewport || window.visualViewport;
  if (vv) {
    vv.addEventListener("resize", reposition, {passive:true});
    vv.addEventListener("scroll", reposition, {passive:true});
  }
})();
</script>
        """,
        height=1,
    )

render_floating_scroll_top()

if st.session_state.get("_scroll_top_once"):
    st.session_state["_scroll_top_once"] = False
    st.session_state["_scroll_top_nonce"] = st.session_state.get("_scroll_top_nonce", 0) + 1
    scroll_to_top(nonce=st.session_state["_scroll_top_nonce"])

# ============================================================
# ✅ Cookies + Supabase Secrets
# ============================================================
cookies = EncryptedCookieManager(
    prefix="hatena_grammar_",
    password=st.secrets["COOKIE_PASSWORD"],
)
if not cookies.ready():
    st.info("잠깐만요! 곧 시작할게요🙂")
    st.stop()

if "SUPABASE_URL" not in st.secrets or "SUPABASE_ANON_KEY" not in st.secrets:
    st.error("Supabase Secrets가 설정되지 않았습니다. (SUPABASE_URL / SUPABASE_ANON_KEY)")
    st.stop()

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_ANON_KEY = st.secrets["SUPABASE_ANON_KEY"]
sb = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# ============================================================
# ✅ 상수/설정
# ============================================================
SHOW_POST_SUBMIT_UI = "N"
SHOW_NAVER_TALK = "Y"
NAVER_TALK_URL = "https://talk.naver.com/W45141"
APP_URL = "https://YOUR_APP_URL.streamlit.app/"  # ✅ 본인 앱 URL로 변경(회원가입 인증 링크 리다이렉트)
KST_TZ = "Asia/Seoul"

N = 10
BASE_DIR = Path(__file__).resolve().parent
CSV_PATH = BASE_DIR / "data" / "grammar.csv"  # ✅ 문법 CSV 파일

LEVEL_OPTIONS = ["N5", "N4", "N3", "N2", "N1"]
LEVEL_LABEL_MAP = {lv: lv for lv in LEVEL_OPTIONS}

QUIZ_TYPE = "meaning"  # 문법뜻 맞히기 1종만

# ============================================================
# ✅ 세션 기본값
# ============================================================
if "level" not in st.session_state:
    st.session_state.level = "N5"
if st.session_state.level not in LEVEL_OPTIONS:
    st.session_state.level = "N5"

# ============================================================
# ✅ Utils: 위젯 잔상(q_...) 제거
# ============================================================
def clear_question_widget_keys():
    keys_to_del = [k for k in list(st.session_state.keys()) if isinstance(k, str) and k.startswith("q_")]
    for k in keys_to_del:
        st.session_state.pop(k, None)

def mastery_key(level: str | None = None) -> str:
    lv = (level or st.session_state.get("level", "N5")).upper()
    return f"{lv}__grammar_meaning"

def ensure_mastered_shape():
    if "mastered_items" not in st.session_state or not isinstance(st.session_state.mastered_items, dict):
        st.session_state.mastered_items = {}
    for lv in LEVEL_OPTIONS:
        st.session_state.mastered_items.setdefault(mastery_key(lv), set())

def ensure_mastery_banner_shape():
    if "mastery_banner_shown" not in st.session_state or not isinstance(st.session_state.mastery_banner_shown, dict):
        st.session_state.mastery_banner_shown = {}
    if "mastery_done" not in st.session_state or not isinstance(st.session_state.mastery_done, dict):
        st.session_state.mastery_done = {}
    for lv in LEVEL_OPTIONS:
        k = mastery_key(lv)
        st.session_state.mastery_banner_shown.setdefault(k, False)
        st.session_state.mastery_done.setdefault(k, False)

# ============================================================
# ✅ Answers 동기화
# ============================================================
def sync_answers_from_widgets():
    qv = st.session_state.get("quiz_version", 0)
    quiz = st.session_state.get("quiz", [])
    if not isinstance(quiz, list):
        return

    answers = st.session_state.get("answers")
    if not isinstance(answers, list) or len(answers) != len(quiz):
        st.session_state.answers = [None] * len(quiz)

    for idx in range(len(quiz)):
        widget_key = f"q_{qv}_{idx}"
        if widget_key in st.session_state:
            st.session_state.answers[idx] = st.session_state[widget_key]

def start_quiz_state(quiz_list: list):
    st.session_state.quiz_version = int(st.session_state.get("quiz_version", 0)) + 1

    if not isinstance(quiz_list, list):
        quiz_list = []
    st.session_state.quiz = quiz_list
    st.session_state.answers = [None] * len(quiz_list)

    st.session_state.submitted = False
    st.session_state.saved_this_attempt = False
    st.session_state.session_stats_applied_this_attempt = False
    st.session_state.wrong_list = []

    # ✅ SFX 1회만
    st.session_state.sfx_played_this_attempt = False

# ============================================================
# ✅ JWT 만료 감지 + refresh + DB 래퍼
# ============================================================
def is_jwt_expired_error(e: Exception) -> bool:
    msg = str(e).lower()
    return ("jwt expired" in msg) or ("pgrst303" in msg)

def clear_auth_everywhere():
    try:
        cookies["access_token"] = ""
        cookies["refresh_token"] = ""
        cookies.save()
    except Exception:
        pass

    for k in [
        "user", "access_token", "refresh_token",
        "login_email", "email_link_notice_shown",
        "auth_mode", "signup_done", "last_signup_ts",
        "page",
        "quiz", "answers", "submitted", "wrong_list",
        "quiz_version",
        "saved_this_attempt",
        "history",
        "attendance_checked", "streak_count", "did_attend_today",
        "is_admin_cached",
        "session_stats_applied_this_attempt",
        "mastered_items", "mastery_banner_shown", "mastery_done",
        "_sb_authed", "_sb_authed_token",
        "pool_ready", "_pool",
        "sfx_played_this_attempt",
    ]:
        st.session_state.pop(k, None)

def run_db(callable_fn):
    try:
        return callable_fn()
    except Exception as e:
        if is_jwt_expired_error(e):
            ok = refresh_session_from_cookie_if_needed(force=True)
            if ok:
                st.rerun()
            clear_auth_everywhere()
            st.warning("세션이 만료되었습니다. 다시 로그인해 주세요.")
            st.rerun()
        raise

def refresh_session_from_cookie_if_needed(force: bool = False) -> bool:
    if not force and st.session_state.get("user") and st.session_state.get("access_token"):
        return True

    rt = cookies.get("refresh_token")
    at = cookies.get("access_token")

    if rt:
        try:
            refreshed = sb.auth.refresh_session(rt)
            if refreshed and refreshed.session and refreshed.session.access_token:
                st.session_state.user = refreshed.user
                st.session_state.access_token = refreshed.session.access_token
                st.session_state.refresh_token = refreshed.session.refresh_token

                u_email = getattr(refreshed.user, "email", None)
                if u_email:
                    st.session_state["login_email"] = u_email.strip()

                cookies["access_token"] = refreshed.session.access_token
                cookies["refresh_token"] = refreshed.session.refresh_token
                cookies.save()
                return True
        except Exception:
            pass

    if at:
        try:
            u = sb.auth.get_user(at)
            user_obj = getattr(u, "user", None) or getattr(u, "data", None) or None
            if user_obj:
                st.session_state.user = user_obj
                st.session_state.access_token = at
                if rt:
                    st.session_state.refresh_token = rt
                u_email = getattr(user_obj, "email", None)
                if u_email:
                    st.session_state["login_email"] = u_email.strip()
                return True
        except Exception:
            pass

    return False

def get_authed_sb():
    if not st.session_state.get("access_token"):
        refresh_session_from_cookie_if_needed(force=True)

    token = st.session_state.get("access_token")
    if not token:
        return None

    cached = st.session_state.get("_sb_authed")
    cached_token = st.session_state.get("_sb_authed_token")

    if cached is not None and cached_token == token:
        return cached

    sb2 = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    sb2.postgrest.auth(token)

    st.session_state["_sb_authed"] = sb2
    st.session_state["_sb_authed_token"] = token
    return sb2

def to_kst_naive(x):
    ts = pd.to_datetime(x, utc=True, errors="coerce")
    if isinstance(ts, pd.Series):
        return ts.dt.tz_convert(KST_TZ).dt.tz_localize(None)
    if pd.isna(ts):
        return ts
    return ts.tz_convert(KST_TZ).tz_localize(None)

# ============================================================
# ✅ DB 함수 (테이블: profiles, quiz_attempts)
# ============================================================
def ensure_profile(sb_authed, user):
    try:
        sb_authed.table("profiles").upsert(
            {"id": user.id, "email": getattr(user, "email", None)},
            on_conflict="id",
        ).execute()
    except Exception:
        pass

def fetch_is_admin_from_db(sb_authed, user_id):
    try:
        res = sb_authed.table("profiles").select("is_admin").eq("id", user_id).single().execute()
        if res and res.data and "is_admin" in res.data:
            return bool(res.data["is_admin"])
    except Exception:
        pass
    return False

def save_attempt_to_db(sb_authed, user_id, user_email, level, quiz_len, score, wrong_list):
    payload = {
        "user_id": user_id,
        "user_email": user_email,
        "level": level,
        "pos_mode": "grammar_meaning",
        "quiz_len": int(quiz_len),
        "score": int(score),
        "wrong_count": int(len(wrong_list)),
        "wrong_list": wrong_list,
    }
    sb_authed.table("quiz_attempts").insert(payload).execute()

def fetch_recent_attempts(sb_authed, user_id, limit=10):
    return (
        sb_authed.table("quiz_attempts")
        .select("created_at, level, pos_mode, quiz_len, score, wrong_count, wrong_list")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )

# ============================================================
# ✅ Admin 설정 (DB ONLY)
# ============================================================
def is_admin() -> bool:
    cached = st.session_state.get("is_admin_cached")
    if cached is not None:
        return bool(cached)

    u = st.session_state.get("user")
    if u is None:
        st.session_state["is_admin_cached"] = False
        return False

    sb_authed_local = get_authed_sb()
    if sb_authed_local is None:
        st.session_state["is_admin_cached"] = False
        return False

    val = fetch_is_admin_from_db(sb_authed_local, u.id)
    st.session_state["is_admin_cached"] = val
    return bool(val)

# ============================================================
# ✅ 로그인 UI
# ============================================================
def auth_box():
    st.markdown("<div style='max-width:520px; margin:0 auto;'>", unsafe_allow_html=True)
    st.markdown(
        '<div class="jp" style="font-weight:900; font-size:16px; margin:6px 0 6px 0;">로그인</div>',
        unsafe_allow_html=True,
    )

    qp = st.query_params
    came_from_email_link = any(k in qp for k in ["code", "token", "type", "access_token", "refresh_token"])
    if came_from_email_link and not st.session_state.get("email_link_notice_shown"):
        st.session_state.email_link_notice_shown = True
        st.session_state.auth_mode = "login"
        st.success("이메일 인증(또는 링크 확인)이 완료되었습니다. 이제 로그인해 주세요.")

    if "auth_mode" not in st.session_state:
        st.session_state.auth_mode = "login"

    mode = st.radio(
        label="",
        options=["login", "signup"],
        format_func=lambda x: "로그인" if x == "login" else "회원가입",
        horizontal=True,
        key="auth_mode_radio",
        index=0 if st.session_state.auth_mode == "login" else 1,
    )
    st.session_state.auth_mode = mode

    if st.session_state.get("signup_done"):
        st.success("회원가입 요청 완료! 이메일 인증이 필요할 수 있어요. 메일함을 확인한 뒤 로그인해 주세요.")
        st.session_state.signup_done = False

    if mode == "login":
        email = st.text_input("이메일", key="login_email_input")
        pw = st.text_input("비밀번호", type="password", key="login_pw_input")

        st.caption("비밀번호는 **회원가입 때 8자리 이상**으로 설정했을 가능성이 큽니다.")
        if pw and len(pw) < 8:
            st.warning(f"입력하신 비밀번호가 {len(pw)}자리입니다. 회원가입 때 8자리 이상으로 설정하셨다면 더 길게 입력해 주세요.")

        if st.button("로그인", use_container_width=True, key="btn_login"):
            if not email or not pw:
                st.warning("이메일과 비밀번호를 입력해주세요.")
                st.stop()
            try:
                res = sb.auth.sign_in_with_password({"email": email, "password": pw})

                st.session_state.user = res.user
                st.session_state["login_email"] = email.strip()

                if res.session and res.session.access_token:
                    st.session_state.access_token = res.session.access_token
                    st.session_state.refresh_token = res.session.refresh_token
                    cookies["access_token"] = res.session.access_token
                    cookies["refresh_token"] = res.session.refresh_token
                    cookies.save()
                else:
                    st.warning("로그인은 되었지만 세션 토큰이 없습니다. 이메일 인증 상태를 확인해주세요.")
                    st.session_state.access_token = None
                    st.session_state.refresh_token = None

                st.session_state.pop("is_admin_cached", None)
                st.success("로그인 완료!")
                st.rerun()
            except Exception:
                st.error("로그인 실패: 이메일/비밀번호 또는 이메일 인증 상태를 확인해주세요.")
                st.stop()

    else:
        email = st.text_input("이메일", key="signup_email")
        pw = st.text_input("비밀번호", type="password", key="signup_pw")

        pw_len = len(pw) if pw else 0
        pw_ok = pw_len >= 8
        email_ok = bool(email and email.strip())

        st.caption("비밀번호는 **8자리 이상**으로 설정해 주세요.")
        if pw and not pw_ok:
            st.warning(f"비밀번호가 너무 짧습니다. (현재 {pw_len}자) 8자리 이상으로 입력해 주세요.")

        if st.button("회원가입", use_container_width=True, disabled=not (email_ok and pw_ok), key="btn_signup"):
            try:
                last = st.session_state.get("last_signup_ts", 0.0)
                now = time.time()
                if now - last < 8:
                    st.warning("요청이 너무 빠릅니다. 잠시 후 다시 시도해주세요.")
                    st.stop()
                st.session_state.last_signup_ts = now

                sb.auth.sign_up(
                    {
                        "email": email,
                        "password": pw,
                        "options": {"email_redirect_to": APP_URL},
                    }
                )

                st.session_state.signup_done = True
                st.session_state.auth_mode = "login"
                st.session_state["login_email"] = email.strip()
                st.rerun()

            except Exception as e:
                msg = str(e).lower()
                if "rate limit" in msg and "email" in msg:
                    st.session_state.auth_mode = "login"
                    st.session_state["login_email"] = email.strip()
                    st.session_state.signup_done = False
                    st.warning("이메일 발송 제한에 걸렸습니다. 잠시 후 다시 시도해주세요.")
                    st.rerun()

                st.error("회원가입 실패(에러 확인):")
                st.exception(e)
                st.stop()

    st.markdown("</div>", unsafe_allow_html=True)

def require_login():
    if st.session_state.get("user") is None:
        st.markdown(
            """
<div class="jp" style="margin: 8px 0 14px 0;">
  <div style="
    border:1px solid rgba(120,120,120,0.18);
    border-radius:18px;
    padding:16px 16px;
    background: rgba(255,255,255,0.03);
  ">
    <div style="font-weight:900; font-size:22px; line-height:1.15;">
      ✨ 문법 퀴즈
    </div>
    <div style="margin-top:6px; opacity:.85; font-size:13px; line-height:1.55;">
      하루 10문항으로 문법 뜻을 루틴처럼 익혀요.<br/>
      정답/오답이 저장되고, 오답만 다시 풀 수 있어요.
    </div>
  </div>
</div>
""",
            unsafe_allow_html=True,
        )
        auth_box()
        st.stop()

# ============================================================
# ✅ 네이버톡 배너 (제출 후만)
# ============================================================
def render_naver_talk():
    st.divider()
    st.markdown(
        f"""
<style>
@keyframes floaty {{
  0% {{ transform: translateY(0); }}
  50% {{ transform: translateY(-6px); }}
  100% {{ transform: translateY(0); }}
}}
@keyframes ping {{
  0% {{ transform: scale(1); opacity: 0.9; }}
  70% {{ transform: scale(2.2); opacity: 0; }}
  100% {{ transform: scale(2.2); opacity: 0; }}
}}
.floating-naver-talk,
.floating-naver-talk:visited,
.floating-naver-talk:hover,
.floating-naver-talk:active {{
  position: fixed;
  right: 18px;
  bottom: 90px;
  z-index: 99999;
  text-decoration: none !important;
  color: inherit !important;
}}
.floating-wrap {{
  position: relative;
  animation: floaty 2.2s ease-in-out infinite;
}}
.talk-btn {{
  background: #03C75A;
  color: #fff;
  border: 0;
  border-radius: 999px;
  padding: 14px 18px;
  font-size: 15px;
  font-weight: 700;
  box-shadow: 0 12px 28px rgba(0,0,0,0.22);
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 10px;
  line-height: 1.1;
  text-decoration: none !important;
}}
.talk-btn:hover {{ filter: brightness(0.95); }}
.talk-text small {{
  display: block;
  font-size: 12px;
  font-weight: 600;
  opacity: 0.95;
  margin-top: 2px;
}}
.badge {{
  position: absolute;
  top: -6px;
  right: -6px;
  width: 12px;
  height: 12px;
  background: #ff3b30;
  border-radius: 999px;
  box-shadow: 0 6px 14px rgba(0,0,0,0.25);
}}
.badge::after {{
  content: "";
  position: absolute;
  left: 50%;
  top: 50%;
  width: 12px;
  height: 12px;
  transform: translate(-50%, -50%);
  border-radius: 999px;
  background: rgba(255,59,48,0.55);
  animation: ping 1.2s ease-out infinite;
}}
@media (max-width: 600px) {{
  .floating-naver-talk {{ bottom: 110px; right: 14px; }}
  .talk-btn {{ padding: 13px 16px; font-size: 14px; }}
  .talk-text small {{ font-size: 11px; }}
}}
</style>

<a class="floating-naver-talk" href="{NAVER_TALK_URL}" target="_blank" rel="noopener noreferrer">
  <div class="floating-wrap">
    <span class="badge"></span>
    <button class="talk-btn" type="button">
      <span>💬</span>
      <span class="talk-text">
        1:1 하테나쌤 상담
        <small>수강신청 문의하기</small>
      </span>
    </button>
  </div>
</a>
""",
        unsafe_allow_html=True,
    )

# ============================================================
# ✅ 상단 카드(관리자/마이페이지/로그아웃)
# ============================================================
def nav_to(page: str, scroll_top: bool = True):
    st.session_state.page = page
    if scroll_top:
        st.session_state["_scroll_top_once"] = True

def nav_logout():
    clear_auth_everywhere()

def render_topcard():
    u = st.session_state.get("user")
    if not u:
        return

    st.markdown('<div class="topcard">', unsafe_allow_html=True)
    left, r_admin, r_my, r_logout = st.columns([6.0, 1.2, 2.4, 2.4], vertical_alignment="center")

    with left:
        st.markdown("<div style='height:40px;'></div>", unsafe_allow_html=True)

    with r_admin:
        if is_admin():
            st.button("📊", use_container_width=True, help="관리자 대시보드",
                      key="topcard_btn_nav_admin", on_click=nav_to, args=("admin",))
        else:
            st.markdown("<div style='height:40px;'></div>", unsafe_allow_html=True)

    with r_my:
        st.button("📌 마이페이지", use_container_width=True, help="내 학습 기록/오답 TOP10 보기",
                  key="topcard_btn_nav_my", on_click=nav_to, args=("my",))

    with r_logout:
        st.button("🚪 로그아웃", use_container_width=True, help="로그아웃",
                  key="topcard_btn_logout", on_click=nav_logout)

    st.markdown("</div>", unsafe_allow_html=True)

# ============================================================
# ✅ 로딩: CSV 풀 (문법용)
# ============================================================
READ_KW = dict(
    dtype=str,
    keep_default_na=False,
    na_values=["nan", "NaN", "NULL", "null", "None", "none"],
)

@st.cache_data(show_spinner=False)
def load_pool(csv_path_str: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path_str, **READ_KW)

    required_cols = {"level", "grammar", "meaning_kr"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"CSV 필수 컬럼 누락: {sorted(list(missing))}")

    def _nfkc(s):
        return unicodedata.normalize("NFKC", str(s or ""))

    lv = df["level"].apply(_nfkc).astype(str).str.upper().str.strip()
    lv = lv.str.replace(" ", "", regex=False)
    extracted = lv.str.extract(r"(N[1-5])", expand=False)

    digit_map = {"1": "N1", "2": "N2", "3": "N3", "4": "N4", "5": "N5"}
    only_digit = lv.where(extracted.isna(), "")
    only_digit = only_digit.str.extract(r"^([1-5])$", expand=False)
    digit_fixed = only_digit.map(digit_map)

    final_lv = extracted.fillna(digit_fixed).fillna(lv)
    final_lv = final_lv.where(final_lv.isin(["N1", "N2", "N3", "N4", "N5"]), "")
    df["level"] = final_lv

    df["grammar"] = df["grammar"].astype(str).str.strip()
    df["meaning_kr"] = df["meaning_kr"].astype(str).str.strip()

    if "example_jp" in df.columns:
        df["example_jp"] = df["example_jp"].astype(str).str.strip()
    else:
        df["example_jp"] = ""

    if "example_kr" in df.columns:
        df["example_kr"] = df["example_kr"].astype(str).str.strip()
    else:
        df["example_kr"] = ""

    # ✅ tag 컬럼(있으면 사용), 없으면 자동 추정
    if "tag" in df.columns:
        df["tag"] = df["tag"].astype(str).str.strip()
    else:
        df["tag"] = df["grammar"].apply(guess_grammar_tag)

    df["tag"] = df["tag"].astype(str).str.strip()
    df.loc[df["tag"] == "", "tag"] = "기본"

    df = df[(df["level"] != "") & (df["grammar"] != "") & (df["meaning_kr"] != "")].copy()
    return df.reset_index(drop=True)

def ensure_pool_ready():
    if st.session_state.get("pool_ready") and isinstance(st.session_state.get("_pool"), pd.DataFrame):
        return
    try:
        pool = load_pool(str(CSV_PATH))
    except Exception as e:
        st.error(f"문법 데이터 로드 실패: {e}")
        st.stop()

    if len(pool) < N:
        st.error(f"데이터가 부족합니다: pool={len(pool)} (N={N})")
        st.stop()

    st.session_state["_pool"] = pool
    st.session_state["pool_ready"] = True

    if is_admin():
        with st.expander("🔎 디버그: 레벨별 문법 수", expanded=False):
            st.write(pool["level"].value_counts(dropna=False))
            st.write("CSV_PATH =", str(CSV_PATH))

# ============================================================
# ✅ 오답(보기) 설계: 정확도(변별) 올리기
# ============================================================
def _norm_kr(s: str) -> str:
    s = str(s or "").strip()
    s = re.sub(r"\s+", " ", s)
    return s

def _tokenize_kr(s: str) -> set:
    s = _norm_kr(s)
    s = re.sub(r"[^\w가-힣]+", " ", s)
    toks = [t for t in s.split(" ") if t]
    return set(toks)

def pick_distractors_meaning_kr(
    pool_level: pd.DataFrame,
    pool_all: pd.DataFrame,
    correct_meaning_kr: str,
    level: str,
    correct_tag: str | None = None,
    k: int = 3,
    recent_key: str = "recent_distractors",
    recent_keep: int = 60,
) -> list[str]:
    correct = _norm_kr(correct_meaning_kr)
    level = str(level or "").upper().strip()
    correct_tag = str(correct_tag or "").strip()

    if recent_key not in st.session_state or not isinstance(st.session_state[recent_key], list):
        st.session_state[recent_key] = []
    recent = st.session_state[recent_key][-recent_keep:]
    recent_set = set(recent)

    def build_candidates(df: pd.DataFrame) -> list[str]:
        xs = (
            df.loc[df["meaning_kr"].astype(str).str.strip() != correct, "meaning_kr"]
            .dropna()
            .astype(str)
            .map(_norm_kr)
            .tolist()
        )
        out, seen = [], set()
        for x in xs:
            if not x or x == correct:
                continue
            if x in seen:
                continue
            seen.add(x)
            out.append(x)
        return out

    # 1) 같은 레벨 + 같은 태그 우선
    tag_pool = None
    if correct_tag:
        try:
            tag_pool = pool_level[pool_level["tag"].astype(str).str.strip() == correct_tag].copy()
        except Exception:
            tag_pool = None

    cands = []
    if tag_pool is not None and len(tag_pool) >= 4:
        cands = build_candidates(tag_pool)

    # 2) 부족하면 같은 레벨 전체
    if len(cands) < k:
        cands = build_candidates(pool_level)

    # 3) 그래도 부족하면 전체풀
    if len(cands) < k:
        cands = build_candidates(pool_all)

    if len(cands) < k:
        return []

    ct = _tokenize_kr(correct)
    def score(x: str) -> int:
        xt = _tokenize_kr(x)
        return len(ct & xt)

    fresh = [x for x in cands if x not in recent_set]
    old = [x for x in cands if x in recent_set]

    fresh.sort(key=score, reverse=True)
    old.sort(key=score, reverse=True)

    top = fresh[: max(24, k * 10)] + old[: max(24, k * 10)]
    top = list(dict.fromkeys(top))

    if len(top) < k:
        top = cands

    picked = random.sample(top, k)
    st.session_state[recent_key] = (st.session_state[recent_key] + picked)[-recent_keep:]
    return picked

# ============================================================
# ✅ 퀴즈 로직: 문법 뜻(4지선다)
# ============================================================
def make_question(row: pd.Series, pool_level: pd.DataFrame) -> dict:
    grammar = str(row.get("grammar", "")).strip()
    meaning_kr = str(row.get("meaning_kr", "")).strip()
    ex_jp = str(row.get("example_jp", "")).strip()
    ex_kr = str(row.get("example_kr", "")).strip()
    lvl = str(row.get("level", "")).strip().upper()

    pool_all = st.session_state["_pool"]
    tag = str(row.get("tag", "")).strip()

    wrongs = pick_distractors_meaning_kr(
        pool_level=pool_level,
        pool_all=pool_all,
        correct_meaning_kr=meaning_kr,
        level=lvl,
        correct_tag=tag,
        k=3,
        recent_key=f"recent_distractors_{lvl}_{tag}",
        recent_keep=120,
    )

    if len(wrongs) < 3:
        st.error(f"오답 후보 부족: level={lvl}, 후보={len(wrongs)}개")
        st.stop()

    choices = wrongs + [meaning_kr]
    random.shuffle(choices)

    prompt = f"「{grammar}」의 뜻은?"
    if ex_jp:
        prompt += f"\n\n예문) {ex_jp}"

    return {
        "prompt": prompt,
        "choices": choices,
        "correct_text": meaning_kr,
        "grammar": grammar,
        "meaning_kr": meaning_kr,
        "example_jp": ex_jp,
        "example_kr": ex_kr,
        "level": lvl,
        "qtype": QUIZ_TYPE,
    }

def build_quiz(level: str) -> list[dict]:
    ensure_pool_ready()
    ensure_mastered_shape()
    ensure_mastery_banner_shape()

    pool = st.session_state["_pool"]
    level = str(level).strip().upper()

    base_level = pool[pool["level"].astype(str).str.upper() == level].copy()
    if len(base_level) < N:
        st.warning(f"{level} 문법이 부족합니다. (현재 {len(base_level)}개 / 필요 {N}개)")
        return []

    k = mastery_key(level)
    mastered = st.session_state.get("mastered_items", {}).get(k, set())

    def _filter_mastered(df: pd.DataFrame) -> pd.DataFrame:
        if not mastered:
            return df
        keys = df["grammar"].astype(str).str.strip()
        return df[~keys.isin(mastered)].copy()

    base = _filter_mastered(base_level)
    if len(base) < N:
        st.session_state.mastery_done[k] = True
        return []

    sampled = base.sample(n=N, replace=False).reset_index(drop=True)
    return [make_question(sampled.iloc[i], base_level) for i in range(N)]

def build_quiz_from_wrongs(wrong_list: list) -> list:
    ensure_pool_ready()
    pool = st.session_state["_pool"]

    wrong_grammars = []
    for w in (wrong_list or []):
        key = str(w.get("문법", "")).strip()
        if key:
            wrong_grammars.append(key)
    wrong_grammars = list(dict.fromkeys(wrong_grammars))

    if not wrong_grammars:
        st.warning("현재 오답 노트가 비어 있어요. 🙂")
        return []

    retry_df = pool[pool["grammar"].isin(wrong_grammars)].copy()
    if len(retry_df) == 0:
        st.error("오답 문법을 풀에서 찾지 못했습니다. (grammar 매칭 확인)")
        st.stop()

    retry_df = retry_df.sample(frac=1).reset_index(drop=True)

    lv = str(retry_df.iloc[0]["level"]).upper()
    pool_level = pool[pool["level"].astype(str).str.upper() == lv].copy()

    return [make_question(retry_df.iloc[i], pool_level) for i in range(len(retry_df))]

# ============================================================
# ✅ 마이페이지/관리자
# ============================================================
def render_admin_dashboard():
    st.subheader("📊 관리자 대시보드")
    if not is_admin():
        st.error("접근 권한이 없습니다.")
        st.session_state.page = "quiz"
        st.stop()

    if st.button("← 돌아가기", use_container_width=True, key="btn_admin_back"):
        st.session_state.page = "quiz"
        st.rerun()

    st.caption("※ 확장 가능(전체 기록 조회 등).")

def render_my_dashboard():
    st.subheader("📌 내 대시보드")

    if st.button("← 돌아가기", use_container_width=True, key="btn_my_back"):
        st.session_state.page = "quiz"
        st.rerun()

    u = st.session_state.get("user")
    if not u:
        st.warning("로그인 정보가 없습니다. 다시 로그인해 주세요.")
        st.session_state.page = "quiz"
        st.stop()

    user_id_local = getattr(u, "id", None)
    if not user_id_local:
        st.warning("유저 ID를 찾지 못했습니다. 다시 로그인해 주세요.")
        st.session_state.page = "quiz"
        st.stop()

    sb_authed_local = get_authed_sb()
    if sb_authed_local is None:
        st.warning("세션 토큰이 없습니다. 다시 로그인해 주세요.")
        return

    def _fetch():
        return fetch_recent_attempts(sb_authed_local, user_id_local, limit=50)

    try:
        res = run_db(_fetch)
    except Exception as e:
        st.info("기록을 불러오지 못했습니다.")
        st.write(str(e))
        return

    if not res.data:
        st.info("아직 저장된 기록이 없습니다. 문제를 풀고 제출하면 기록이 쌓여요.")
        return

    hist = pd.DataFrame(res.data).copy()
    hist["created_at"] = to_kst_naive(hist["created_at"])
    hist["정답률"] = (hist["score"] / hist["quiz_len"]).fillna(0.0)

    avg_rate = float(hist["정답률"].mean() * 100)
    best = int(hist["score"].max())
    last_score = int(hist.iloc[0]["score"])
    last_total = int(hist.iloc[0]["quiz_len"])

    dashboard_html = f"""
    <style>
    .stat-grid{{
      display:grid;
      grid-template-columns: repeat(3, 1fr);
      gap:12px;
      margin: 6px 0 6px 0;
    }}
    .stat-card{{
      border:1px solid rgba(120,120,120,0.25);
      border-radius:18px;
      padding:14px 14px;
      background: rgba(255,255,255,0.02);
    }}
    .stat-label{{
      font-size:12px;
      font-weight:800;
      opacity:.72;
      line-height:1.2;
    }}
    .stat-value{{
      margin-top:6px;
      font-size:22px;
      font-weight:900;
      line-height:1.1;
    }}
    .stat-sub{{
      margin-top:6px;
      font-size:12px;
      opacity:.70;
      line-height:1.2;
    }}
    @media (max-width: 520px){{
      .stat-grid{{ grid-template-columns: 1fr; }}
      .stat-value{{ font-size:24px; }}
    }}
    </style>

    <div class="jp">
      <div class="stat-grid">
        <div class="stat-card">
          <div class="stat-label">최근 평균(최대 50회)</div>
          <div class="stat-value">{avg_rate:.0f}%</div>
          <div class="stat-sub">정답률 기준</div>
        </div>

        <div class="stat-card">
          <div class="stat-label">최고 점수</div>
          <div class="stat-value">{best} / {last_total}</div>
          <div class="stat-sub">최근 기록 중 최고</div>
        </div>

        <div class="stat-card">
          <div class="stat-label">최근 점수</div>
          <div class="stat-value">{last_score} / {last_total}</div>
          <div class="stat-sub">가장 최근 1회</div>
        </div>
      </div>
    </div>
    """
    components.html(dashboard_html, height=330)

    st.markdown("### ❌ 자주 틀린 문법 TOP10 (최근 50회)")
    counter = Counter()
    for row in (res.data or []):
        wl = row.get("wrong_list") or []
        if isinstance(wl, list):
            for w in wl:
                g = str(w.get("문법", "")).strip()
                if g:
                    counter[g] += 1

    if not counter:
        st.caption("아직 오답 데이터가 충분하지 않습니다. 몇 번 더 풀면 TOP10이 생겨요 🙂")
        return

    st.markdown("""
    <style>
    .wt10-card{
      border:1px solid rgba(120,120,120,0.25);
      border-radius:18px;
      padding:14px 16px;
      margin:12px 0;
      background: rgba(255,255,255,0.02);
      display:flex;
      align-items:center;
      justify-content:space-between;
      gap:14px;
    }
    .wt10-left{
      display:flex;
      flex-direction:column;
      gap:6px;
      min-width: 0;
    }
    .wt10-title{
      font-size:18px;
      font-weight:900;
      line-height:1.15;
      overflow:hidden;
      text-overflow:ellipsis;
      white-space:nowrap;
    }
    .wt10-sub{
      font-size:13px;
      opacity:.75;
    }
    .wt10-badge{
      border:1px solid rgba(120,120,120,0.25);
      background: rgba(255,255,255,0.03);
      border-radius:999px;
      padding:7px 12px;
      font-size:13px;
      font-weight:900;
      white-space:nowrap;
    }
    </style>
    """, unsafe_allow_html=True)

    def render_wrong_top10_card(rank: int, grammar: str, cnt: int):
        st.markdown(f"""
    <div class="jp">
      <div class="wt10-card">
        <div class="wt10-left">
          <div class="wt10-title">#{rank} {grammar}</div>
          <div class="wt10-sub">최근 50회 기준</div>
        </div>
        <div class="wt10-badge">오답 {cnt}회</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    top10 = counter.most_common(10)
    for i, (g, cnt) in enumerate(top10, start=1):
        render_wrong_top10_card(i, str(g), int(cnt))

    if st.button("❌ 이 TOP10으로 시험 보기", type="primary", use_container_width=True, key="btn_quiz_from_top10"):
        clear_question_widget_keys()
        weak_wrong_list = [{"문법": g} for (g, _cnt) in top10]
        retry_quiz = build_quiz_from_wrongs(weak_wrong_list)

        k = mastery_key(st.session_state.level)
        st.session_state.mastery_done[k] = False

        start_quiz_state(retry_quiz)
        st.session_state["_scroll_top_once"] = True
        st.session_state.page = "quiz"
        st.rerun()

def reset_quiz_state_only():
    clear_question_widget_keys()
    for k in ["quiz", "answers", "submitted", "wrong_list",
              "saved_this_attempt", "session_stats_applied_this_attempt"]:
        st.session_state.pop(k, None)

def go_quiz_from_home():
    reset_quiz_state_only()
    st.session_state.page = "quiz"
    st.session_state["_scroll_top_once"] = True

def render_home():
    u = st.session_state.get("user")
    email = (getattr(u, "email", None) if u else None) or st.session_state.get("login_email", "")

    st.markdown(
        f"""
<div class="jp headbar">
  <div class="headtitle">✨하테나일본어 문법정복</div>
  <div class="headhello">환영합니다 🙂 <span class="mail">{email}</span></div>
</div>
""",
        unsafe_allow_html=True,
    )

    quotes = [
        "오늘의 10문항이, 내일의 말문을 연다.",
        "문법은 ‘이해’보다 ‘반복’이 강하다.",
        "조금이라도 한 날은, 이미 이긴 날이다.",
        "완벽보다 계속.",
        "작게 시작하고, 길게 간다.",
    ]
    q = random.choice(quotes)

    st.markdown(
        f"""
<div class="jp" style="
  margin-top:1px;
  border:1px solid rgba(120,120,120,0.18);
  border-radius:18px; padding:16px; background:rgba(255,255,255,0.03);">
  <div style="font-weight:900; font-size:14px; opacity:.75;">오늘의 말</div>
  <div style="margin-top:6px; font-weight:900; font-size:20px; line-height:1.3;">{q}</div>
  <div style="margin-top:10px; opacity:.80; font-size:13px; line-height:1.55;">
    오늘은 문법 뜻 10개만, 가볍게 가볼까요?
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    st.divider()

    c1, c2, c3 = st.columns([5, 3, 3])
    with c1:
        st.button("▶ 오늘의 퀴즈 시작", type="primary", use_container_width=True,
                  key="btn_home_start", on_click=go_quiz_from_home)
    with c2:
        st.button("📌 마이페이지", use_container_width=True,
                  key="btn_home_my", on_click=nav_to, args=("my",))
    with c3:
        st.button("🚪 로그아웃", use_container_width=True,
                  key="btn_home_logout", on_click=nav_logout)

# ============================================================
# ✅ 앱 시작: refresh → 로그인 → 라우팅
# ============================================================
ok = refresh_session_from_cookie_if_needed(force=False)
if not ok and (cookies.get("refresh_token") or cookies.get("access_token")):
    clear_auth_everywhere()
    st.caption("세션 복원에 실패해서 로그인을 다시 요청합니다.")

require_login()

ALLOWED_PAGES = {"home", "quiz", "my", "admin"}
if "page" not in st.session_state:
    st.session_state.page = "home"
if st.session_state.get("page") not in ALLOWED_PAGES:
    st.session_state.page = "home"

user = st.session_state.user
user_id = user.id
user_email = getattr(user, "email", None) or st.session_state.get("login_email")
sb_authed = get_authed_sb()

if st.session_state.get("page") != "home":
    email = getattr(user, "email", None) or st.session_state.get("login_email", "")
    st.markdown(
        f"""
<div class="jp headbar">
  <div class="headtitle">✨ 문법 퀴즈</div>
  <div class="headhello">환영합니다 🙂 <span class="mail">{email}</span></div>
</div>
""",
        unsafe_allow_html=True,
    )

if sb_authed is not None:
    ensure_profile(sb_authed, user)
else:
    st.caption("세션 토큰이 없습니다. 다시 로그인해 주세요.")

# ============================================================
# ✅ 라우팅
# ============================================================
if st.session_state.page == "home":
    render_home()
    st.stop()

if st.session_state.page == "admin":
    if not is_admin():
        st.session_state.page = "quiz"
        st.warning("관리자 권한이 없습니다.")
        st.rerun()
    render_admin_dashboard()
    st.stop()

if st.session_state.page == "my":
    try:
        render_my_dashboard()
    except Exception:
        st.error("마이페이지에서 예외가 발생했습니다. 아래 Traceback을 확인해 주세요.")
        st.code(traceback.format_exc())
    st.stop()

# ============================================================
# ✅ Quiz Page
# ============================================================
render_topcard()
render_sound_toggle()

# ============================================================
# ✅ 세션 초기화
# ============================================================
if "quiz_version" not in st.session_state:
    st.session_state.quiz_version = 0
if "submitted" not in st.session_state:
    st.session_state.submitted = False
if "wrong_list" not in st.session_state:
    st.session_state.wrong_list = []
if "saved_this_attempt" not in st.session_state:
    st.session_state.saved_this_attempt = False
if "session_stats_applied_this_attempt" not in st.session_state:
    st.session_state.session_stats_applied_this_attempt = False
if "sfx_played_this_attempt" not in st.session_state:
    st.session_state.sfx_played_this_attempt = False

ensure_mastered_shape()
ensure_mastery_banner_shape()

# ============================================================
# ✅ 레벨 선택 UI
# ============================================================
def on_pick_level(lv: str):
    lv = str(lv).strip().upper()
    if lv == st.session_state.level:
        return
    st.session_state.level = lv

    clear_question_widget_keys()
    new_quiz = build_quiz(st.session_state.level)
    start_quiz_state(new_quiz)
    st.session_state["_scroll_top_once"] = True

st.markdown('<div class="qtypewrap">', unsafe_allow_html=True)

level_cols = st.columns(len(LEVEL_OPTIONS), gap="small")
for i, lv in enumerate(LEVEL_OPTIONS):
    is_selected_lv = (lv == st.session_state.level)
    btn_lv_type = "primary" if is_selected_lv else "secondary"
    icon_lv = "✅ " if is_selected_lv else ""
    label_lv = LEVEL_LABEL_MAP.get(lv, lv)

    with level_cols[i]:
        st.button(
            f"{icon_lv}{label_lv}",
            use_container_width=True,
            type=btn_lv_type,
            key=f"btn_level_{lv}",
            on_click=on_pick_level,
            args=(lv,),
        )

st.markdown('<div class="qtype_hint jp">✨레벨을 선택하세요</div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="tight-divider">', unsafe_allow_html=True)
st.divider()
st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# ✅ 버튼: 새 문제 / 맞힌 문법 제외 초기화
# ============================================================
cbtn1, cbtn2 = st.columns(2)
with cbtn1:
    if st.button("🔄 새 문제(랜덤 10문항)", use_container_width=True, key="btn_new_random_10"):
        k_now = mastery_key(st.session_state.level)
        if st.session_state.get("mastery_done", {}).get(k_now, False):
            st.session_state["_scroll_top_once"] = True
            st.rerun()

        clear_question_widget_keys()
        new_quiz = build_quiz(st.session_state.level)
        start_quiz_state(new_quiz)
        st.session_state["_scroll_top_once"] = True
        st.rerun()

with cbtn2:
    if st.button("✅ 맞힌 문법 제외 초기화", use_container_width=True, key="btn_reset_mastered_level"):
        ensure_mastered_shape()
        k_now = mastery_key(st.session_state.level)
        st.session_state.mastered_items[k_now] = set()
        st.session_state.mastery_banner_shown[k_now] = False
        st.session_state.mastery_done[k_now] = False

        clear_question_widget_keys()
        new_quiz = build_quiz(st.session_state.level)
        start_quiz_state(new_quiz)

        st.success(f"초기화 완료 (레벨: {st.session_state.level})")
        st.session_state["_scroll_top_once"] = True
        st.rerun()

k_now = mastery_key(st.session_state.level)
if st.session_state.get("mastery_done", {}).get(k_now, False):
    st.success("🏆 이 레벨 문법을 완전히 정복했어요!")
    st.caption("👉 다른 레벨을 선택하거나, '맞힌 문법 제외 초기화'로 다시 시작할 수 있어요.")

# ============================================================
# ✅ 퀴즈 생성(1회 자동)
# ============================================================
if "quiz" not in st.session_state or not isinstance(st.session_state.quiz, list):
    st.session_state.quiz = []

is_mastered_done = bool(st.session_state.get("mastery_done", {}).get(k_now, False))
if (not is_mastered_done) and len(st.session_state.quiz) == 0:
    clear_question_widget_keys()
    st.session_state.quiz = build_quiz(st.session_state.level) or []
    st.session_state.submitted = False

if len(st.session_state.quiz) == 0:
    st.info("이 레벨에 출제할 문법이 없어요. 다른 레벨을 선택하거나, CSV의 level 값을 확인해 주세요.")
    st.stop()

quiz_len = len(st.session_state.quiz)
if "answers" not in st.session_state or not isinstance(st.session_state.answers, list) or len(st.session_state.answers) != quiz_len:
    st.session_state.answers = [None] * quiz_len

if bool(st.session_state.get("mastery_done", {}).get(k_now, False)):
    st.stop()

# ============================================================
# ✅ 문제 표시
# ============================================================
for idx, q in enumerate(st.session_state.quiz):
    st.subheader(f"Q{idx+1}")

    st.markdown(
        f'<div class="jp" style="margin-top:-6px; margin-bottom:6px; font-size:18px; font-weight:500; line-height:1.35;">{q["prompt"]}</div>',
        unsafe_allow_html=True,
    )

    widget_key = f"q_{st.session_state.quiz_version}_{idx}"
    prev = st.session_state.answers[idx]
    default_index = None
    if prev is not None and prev in q["choices"]:
        default_index = q["choices"].index(prev)

    choice = st.radio(
        label="보기",
        options=q["choices"],
        index=default_index,
        key=widget_key,
        label_visibility="collapsed",
    )
    st.session_state.answers[idx] = choice

sync_answers_from_widgets()

# ============================================================
# ✅ 제출/채점
# ============================================================
all_answered = (quiz_len > 0) and all(a is not None for a in st.session_state.answers)

if st.button("✅ 제출하고 채점하기", disabled=not all_answered, type="primary", use_container_width=True, key="btn_submit"):
    st.session_state.submitted = True
    st.session_state.session_stats_applied_this_attempt = False

if not all_answered:
    st.info("모든 문제에 답을 선택하면 제출 버튼이 활성화됩니다.")

# ============================================================
# ✅ 제출 후 화면
# ============================================================
if st.session_state.submitted:
    ensure_mastered_shape()
    current_level = st.session_state.level
    k_now = mastery_key(current_level)

    score = 0
    wrong_list = []

    for idx, q in enumerate(st.session_state.quiz):
        picked = st.session_state.answers[idx]
        correct = q["correct_text"]
        grammar_key = str(q.get("grammar", "")).strip()

        if picked == correct:
            score += 1
            if grammar_key:
                st.session_state.mastered_items.setdefault(k_now, set()).add(grammar_key)
        else:
            wrong_list.append({
                "No": idx + 1,
                "문제": f"「{q.get('grammar','')}」의 뜻은?",
                "내 답": "" if picked is None else str(picked),
                "정답": str(correct),
                "문법": str(q.get("grammar", "")).strip(),
                "예문": str(q.get("example_jp", "")).strip(),
                "예문해석": str(q.get("example_kr", "")).strip(),
                "레벨": current_level,
            })

    st.session_state.wrong_list = wrong_list

    st.success(f"점수: {score} / {quiz_len}")
    ratio = score / quiz_len if quiz_len else 0

    if not st.session_state.get("sfx_played_this_attempt", False):
        if ratio == 1:
            sfx("perfect")
        elif ratio >= 0.7:
            sfx("correct")
        else:
            sfx("wrong")
        st.session_state.sfx_played_this_attempt = True

    if ratio == 1:
        st.balloons()
        st.success("🎉 완벽해요! 전부 정답입니다. 정말 잘했어요!")
        st.caption("※ 정복 판정은 ‘더 이상 출제할 문법이 없을 때’ 자동으로 표시됩니다.")
    elif ratio >= 0.7:
        st.info("👍 잘하고 있어요! 조금만 더 다듬으면 완벽해질 거예요.")
    else:
        st.warning("💪 괜찮아요! 틀린 문제는 성장의 재료예요. 다시 한 번 도전해봐요.")

    sb_authed_local = get_authed_sb()
    if sb_authed_local is None:
        st.warning("DB 저장용 토큰이 없습니다. 다시 로그인해 주세요.")
    else:
        if not st.session_state.saved_this_attempt:
            def _save():
                return save_attempt_to_db(
                    sb_authed=sb_authed_local,
                    user_id=user_id,
                    user_email=user_email,
                    level=current_level,
                    quiz_len=quiz_len,
                    score=score,
                    wrong_list=wrong_list,
                )
            try:
                run_db(_save)
                st.session_state.saved_this_attempt = True
            except Exception as e:
                st.warning("DB 저장에 실패했습니다. (테이블/컬럼/권한/RLS 정책 확인 필요)")
                st.write(str(e))

# ============================================================
# ✅ 오답노트 + 다시풀기
# ============================================================
if st.session_state.submitted and st.session_state.wrong_list:
    st.subheader("❌ 오답 노트")

    st.markdown(
        """
<style>
.wrong-card{
  border: 1px solid rgba(120,120,120,0.25);
  border-radius: 16px;
  padding: 14px 14px;
  margin-bottom: 10px;
  background: rgba(255,255,255,0.02);
}
.wrong-top{
  display:flex;
  align-items:flex-start;
  justify-content:space-between;
  gap:12px;
  margin-bottom: 8px;
}
.wrong-title{ font-weight: 900; font-size: 15px; margin-bottom: 4px; }
.wrong-sub{ opacity: 0.8; font-size: 12px; }
.tag{
  display:inline-flex;
  align-items:center;
  gap:6px;
  padding: 5px 9px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  border: 1px solid rgba(120,120,120,0.25);
  background: rgba(255,255,255,0.03);
  white-space: nowrap;
}
.ans-row{
  display:grid;
  grid-template-columns: 72px 1fr;
  gap:10px;
  margin-top:6px;
  font-size: 13px;
}
.ans-k{ opacity: 0.7; font-weight: 700; }
</style>
""",
        unsafe_allow_html=True,
    )

    def _h(x):
        s = "" if x is None else str(x)
        s = html.escape(s, quote=True)
        return s.replace("\n", "<br/>")

    def _s(v):
        return "" if v is None else str(v)

    for w in st.session_state.wrong_list:
        no = _s(w.get("No"))
        grammar = _s(w.get("문법"))
        picked = _s(w.get("내 답"))
        correct = _s(w.get("정답"))
        ex = _s(w.get("예문"))
        exkr = _s(w.get("예문해석"))

        card_html = f"""
    <div class="jp">
      <div class="wrong-card">
        <div class="wrong-top">
          <div>
            <div class="wrong-title">Q{_h(no)}. {_h(grammar)}</div>
            <div class="wrong-sub">레벨: {_h(st.session_state.level)}</div>
          </div>
          <div class="tag">오답</div>
        </div>

        <div class="ans-row"><div class="ans-k">내 답</div><div>{_h(picked)}</div></div>
        <div class="ans-row"><div class="ans-k">정답</div><div><b>{_h(correct)}</b></div></div>
        {f'<div class="ans-row"><div class="ans-k">예문</div><div>{_h(ex)}</div></div>' if ex else ''}
        {f'<div class="ans-row"><div class="ans-k">해석</div><div>{_h(exkr)}</div></div>' if exkr else ''}
      </div>
    </div>
    """.strip()

        # ✅ 마크다운 코드블록 방지: 각 줄 앞 공백 제거
        card_html = "\n".join(line.lstrip() for line in card_html.splitlines())

        st.markdown(card_html, unsafe_allow_html=True)


    if st.button("❌ 틀린 문제만 다시 풀기", type="primary", use_container_width=True, key="btn_retry_wrongs_bottom"):
        clear_question_widget_keys()
        retry_quiz = build_quiz_from_wrongs(st.session_state.wrong_list)
        start_quiz_state(retry_quiz)
        st.session_state["_scroll_top_once"] = True
        st.rerun()


    show_naver_talk = (SHOW_NAVER_TALK == "Y") or is_admin()
    if show_naver_talk:
        render_naver_talk()
