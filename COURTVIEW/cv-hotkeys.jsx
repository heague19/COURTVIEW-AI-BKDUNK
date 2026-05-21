// =============================================================================
// COURTVIEW — Hotkey system
// useHotkeys(map)        — bind a map of "key" → handler. Map can be empty.
// useGlobalHotkeys(nav)  — page-level shortcuts (?, g+letter for nav, Esc)
// CvHotkeySheet          — cheat sheet modal (toggled with '?')
// =============================================================================

// ----- normalize key event -----
function keyOf(e) {
  // returns a normalized token like "shift+q", "space", "?", "arrowleft"
  const k = (e.key || "").toLowerCase();
  const parts = [];
  if (e.ctrlKey || e.metaKey) parts.push("mod");
  if (e.shiftKey && k.length > 1) parts.push("shift");      // shift on letters → uppercased already; we treat as base
  if (e.altKey) parts.push("alt");
  // for letters, shift is implicit in the key (e.g. shift+q gives "Q") — normalize
  let main = k;
  if (k.length === 1 && k >= "A" && k <= "Z") main = k.toLowerCase();
  if (e.shiftKey && k.length === 1) parts.push("shift");
  parts.push(main);
  return parts.join("+");
}

function isTypingTarget(el) {
  if (!el) return false;
  const tag = (el.tagName || "").toLowerCase();
  if (tag === "input" || tag === "textarea" || tag === "select") return true;
  if (el.isContentEditable) return true;
  return false;
}

// ----- single-key hotkey hook -----
// map: { "q": fn, "shift+q": fn, "space": fn, ... }
// disabled: bool to temporarily disable
function useHotkeys(map, opts = {}) {
  const { disabled = false } = opts;
  const ref = React.useRef(map);
  ref.current = map;
  React.useEffect(() => {
    if (disabled) return;
    const handler = (e) => {
      if (isTypingTarget(e.target)) return;
      const m = ref.current || {};
      // try exact match, including shift form
      const key = keyOf(e);
      // also try without shift (some shortcuts are case-insensitive)
      const fn = m[key] || m[key.replace("shift+", "")];
      if (fn) {
        e.preventDefault();
        fn(e);
      }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [disabled]);
}

// ----- global hotkeys (sheet, nav-prefix, esc) -----
// onNav(slug) — called for "g h", "g s", etc.
function useGlobalHotkeys({ onNav, onShowSheet, onEscape } = {}) {
  const seqRef = React.useRef({ pending: null, timer: null });
  React.useEffect(() => {
    const h = (e) => {
      if (isTypingTarget(e.target)) return;
      const k = (e.key || "").toLowerCase();

      // ? → cheat sheet
      if (k === "?" || (e.shiftKey && k === "/")) {
        e.preventDefault();
        onShowSheet && onShowSheet();
        return;
      }
      // Esc → close
      if (k === "escape") {
        onEscape && onEscape();
        return;
      }
      // g + letter sequence (vim-style)
      if (seqRef.current.pending === "g") {
        const map = { h: "home", s: "scoreboard", a: "analysis", o: "operator", r: "results", d: "database", t: "timeline", c: "comparison", q: "result-detail" };
        if (map[k]) {
          e.preventDefault();
          onNav && onNav(map[k]);
        }
        clearTimeout(seqRef.current.timer);
        seqRef.current.pending = null;
        return;
      }
      if (k === "g") {
        seqRef.current.pending = "g";
        clearTimeout(seqRef.current.timer);
        seqRef.current.timer = setTimeout(() => { seqRef.current.pending = null; }, 1200);
        // do NOT preventDefault — user might be typing
      }
    };
    document.addEventListener("keydown", h);
    return () => document.removeEventListener("keydown", h);
  }, [onNav, onShowSheet, onEscape]);
}

// ----- toast on hotkey fire -----
function flashHotkey(label) {
  const id = "__cv-hotkey-flash";
  let el = document.getElementById(id);
  if (!el) {
    el = document.createElement("div");
    el.id = id;
    el.style.cssText = `
      position: fixed; left: 50%; bottom: 24px; transform: translateX(-50%);
      background: var(--bg-1); border: 1px solid var(--hot); color: var(--hot);
      font-family: var(--f-mono); font-size: 11px; font-weight: 700; letter-spacing: 1.5px;
      padding: 8px 16px; z-index: 9999; pointer-events: none; transition: opacity 0.15s;
    `;
    document.body.appendChild(el);
  }
  el.textContent = label;
  el.style.opacity = "1";
  clearTimeout(el.__t);
  el.__t = setTimeout(() => { el.style.opacity = "0"; }, 800);
}

// =============================================================================
// CvHotkeySheet — cheat sheet modal
// sections: [{title, items: [{keys: ["Q"], desc: "..."}]}]
// =============================================================================
function CvHotkeySheet({ open, onClose, context = "global" }) {
  if (!open) return null;

  const globalSec = {
    title: "GLOBAL · 어디서나",
    items: [
      { keys: ["?"], desc: "단축키 시트 열기/닫기" },
      { keys: ["Esc"], desc: "모달·다이얼로그 닫기" },
      { keys: ["g", "h"], desc: "→ Home" },
      { keys: ["g", "s"], desc: "→ Scoreboard" },
      { keys: ["g", "a"], desc: "→ Analysis (라이브)" },
      { keys: ["g", "r"], desc: "→ Results" },
      { keys: ["g", "o"], desc: "→ Operator" },
      { keys: ["g", "d"], desc: "→ Database" },
      { keys: ["g", "t"], desc: "→ Timeline" },
      { keys: ["g", "c"], desc: "→ Comparison" },
      { keys: ["g", "q"], desc: "→ Result detail" },
    ],
  };

  const opSec = {
    title: "OPERATOR · 라이브 컨트롤",
    items: [
      { keys: ["Space"], desc: "게임 클락 START / STOP", hot: true },
      { keys: ["R"], desc: "샷 클락 24 리셋" },
      { keys: ["T"], desc: "샷 클락 14 리셋" },
      { keys: ["B"], desc: "부저 (1초 작동)" },
      { keys: ["1", "2", "3", "4", "5"], desc: "쿼터 선택 (5 = OT)" },
      { keys: ["H"], desc: "VOLTS 공격권" },
      { keys: ["L"], desc: "BLAZERS 공격권" },
    ],
  };

  const opScoreSec = {
    title: "OPERATOR · 점수 (좌·우 대칭)",
    items: [
      { keys: ["Q"], desc: "VOLTS +1", color: "var(--hot)" },
      { keys: ["W"], desc: "VOLTS +2", color: "var(--hot)" },
      { keys: ["E"], desc: "VOLTS +3", color: "var(--hot)" },
      { keys: ["⇧Q", "⇧W", "⇧E"], desc: "VOLTS −1 / −2 / −3 (정정)", color: "var(--hot)" },
      { keys: ["O"], desc: "BLAZERS +1", color: "var(--cool)" },
      { keys: ["P"], desc: "BLAZERS +2", color: "var(--cool)" },
      { keys: ["["], desc: "BLAZERS +3", color: "var(--cool)" },
      { keys: ["⇧O", "⇧P", "⇧["], desc: "BLAZERS −1 / −2 / −3", color: "var(--cool)" },
    ],
  };

  const opMiscSec = {
    title: "OPERATOR · 파울 · 타임아웃",
    items: [
      { keys: ["F"], desc: "VOLTS 파울 +1", color: "var(--hot)" },
      { keys: ["⇧F"], desc: "VOLTS 파울 −1", color: "var(--hot)" },
      { keys: ["J"], desc: "BLAZERS 파울 +1", color: "var(--cool)" },
      { keys: ["⇧J"], desc: "BLAZERS 파울 −1", color: "var(--cool)" },
      { keys: ["D"], desc: "VOLTS 작전 요청" },
      { keys: ["K"], desc: "BLAZERS 작전 요청" },
    ],
  };

  const calibrateSec = {
    title: "CALIBRATE · 캠 보정",
    items: [
      { keys: ["S"], desc: "현재 포인트 스킵 → 다음" },
      { keys: ["⌘Z"], desc: "마지막 포인트 취소" },
      { keys: ["우클릭"], desc: "포인트 삭제 (캔버스 위)" },
    ],
  };

  const scoreboardSec = {
    title: "SCOREBOARD · 전광판",
    items: [
      { keys: ["F"], desc: "풀스크린 토글" },
    ],
  };

  const sections = [globalSec, opSec, opScoreSec, opMiscSec, calibrateSec, scoreboardSec];

  return (
    <div onClick={onClose} style={{
      position: "fixed", inset: 0, background: "rgba(0,0,0,0.7)", backdropFilter: "blur(8px)",
      zIndex: 9000, display: "flex", alignItems: "center", justifyContent: "center", padding: 40,
    }}>
      <div onClick={(e) => e.stopPropagation()} style={{
        background: "var(--bg-0)", border: "1px solid var(--line-3)", maxWidth: 1100, width: "100%",
        maxHeight: "92vh", overflow: "hidden", display: "flex", flexDirection: "column",
        boxShadow: "0 30px 60px rgba(0,0,0,0.6)",
      }}>
        {/* Header — editorial style */}
        <div style={{ padding: "26px 36px 18px", borderBottom: "1px solid var(--line-2)", position: "relative" }}>
          <div style={{ position: "absolute", top: 24, right: 36, fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-3)", letterSpacing: 1.4, textAlign: "right" }}>
            <div>REF · 001</div>
            <div style={{ marginTop: 3 }}>KEYBOARD CONTROL</div>
          </div>
          <div style={{ display: "flex", gap: 10, alignItems: "center", marginBottom: 8 }}>
            <span className="cv-tag hot">HOTKEYS</span>
            <span style={{ fontFamily: "var(--f-mono)", fontSize: 11, color: "var(--fg-2)", letterSpacing: 1 }}>BUILT FOR THE LIVE TABLE</span>
          </div>
          <h1 style={{ fontFamily: "var(--f-display)", fontSize: 44, fontWeight: 700, letterSpacing: -1.4, lineHeight: 0.95, marginBottom: 6 }}>
            손은 키보드에,<br/>
            <span style={{ color: "var(--hot)" }}>눈은 코트에.</span>
          </h1>
          <div style={{ fontFamily: "var(--f-mono)", fontSize: 11, color: "var(--fg-2)", letterSpacing: 0.5 }}>
            라이브 운영자는 마우스를 잡을 시간이 없다 — 양손이 점수, 클락, 부저 위에 놓이도록 매핑됨.
          </div>
        </div>

        {/* Sections grid */}
        <div style={{ flex: 1, overflow: "auto", padding: "28px 36px", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 1, background: "var(--line-2)" }}>
          {sections.map((s, i) => (
            <div key={i} style={{ background: "var(--bg-0)", padding: "20px 24px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
                <span style={{ fontFamily: "var(--f-mono)", fontSize: 9, color: "var(--fg-2)", letterSpacing: 2 }}>0{i+1}</span>
                <span style={{ fontFamily: "var(--f-display)", fontSize: 14, fontWeight: 700, letterSpacing: -0.2 }}>{s.title}</span>
                <span style={{ flex: 1, height: 1, background: "var(--line-2)" }}></span>
              </div>
              <div style={{ display: "grid", gap: 8 }}>
                {s.items.map((it, ii) => (
                  <div key={ii} style={{ display: "grid", gridTemplateColumns: "auto 1fr", alignItems: "center", gap: 14, padding: "4px 0" }}>
                    <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                      {it.keys.map((k, ki) => (
                        <kbd key={ki} style={{
                          fontFamily: "var(--f-mono)", fontSize: 10, fontWeight: 700,
                          padding: "3px 8px", minWidth: 22, textAlign: "center",
                          background: it.hot ? "var(--hot)" : (it.color === "var(--hot)" ? "rgba(255,123,46,0.12)" : it.color === "var(--cool)" ? "rgba(77,163,255,0.14)" : "var(--bg-2)"),
                          border: `1px solid ${it.hot ? "var(--hot)" : (it.color || "var(--line-3)")}`,
                          color: it.hot ? "#0A0B0D" : (it.color || "var(--fg-0)"),
                          letterSpacing: 0.5, lineHeight: 1.4, display: "inline-block",
                        }}>{k}</kbd>
                      ))}
                    </div>
                    <span style={{ fontFamily: "var(--f-sans)", fontSize: 12, color: "var(--fg-1)", letterSpacing: 0.2 }}>{it.desc}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Footer */}
        <div style={{ padding: "14px 36px", borderTop: "1px solid var(--line-2)", display: "flex", justifyContent: "space-between", alignItems: "center", fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", letterSpacing: 1 }}>
          <span>입력 필드(input/textarea) 안에서는 비활성화 — 타이핑 보호</span>
          <span><kbd style={{ fontFamily: "inherit", fontSize: 10, padding: "2px 6px", background: "var(--bg-2)", border: "1px solid var(--line-3)", color: "var(--fg-1)" }}>Esc</kbd> 또는 배경 클릭 — 닫기</span>
        </div>
      </div>
    </div>
  );
}

// ----- floating "?" hint button (small, dismissable) -----
function CvHotkeyHint({ onClick }) {
  return (
    <button onClick={onClick} title="단축키 (?)" style={{
      position: "fixed", right: 16, bottom: 16, zIndex: 50,
      width: 36, height: 36, borderRadius: 0,
      background: "var(--bg-1)", border: "1px solid var(--line-3)",
      color: "var(--fg-1)", cursor: "pointer",
      fontFamily: "var(--f-mono)", fontSize: 14, fontWeight: 700,
      transition: "all 0.15s",
    }}
    onMouseEnter={(e) => { e.currentTarget.style.borderColor = "var(--hot)"; e.currentTarget.style.color = "var(--hot)"; }}
    onMouseLeave={(e) => { e.currentTarget.style.borderColor = "var(--line-3)"; e.currentTarget.style.color = "var(--fg-1)"; }}
    >?</button>
  );
}

Object.assign(window, { useHotkeys, useGlobalHotkeys, flashHotkey, CvHotkeySheet, CvHotkeyHint });
