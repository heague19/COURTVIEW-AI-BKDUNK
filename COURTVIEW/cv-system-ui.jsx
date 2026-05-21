// =============================================================================
// COURTVIEW — System UI primitives (Editorial tone)
// EmptyState · Skeleton · Toast · Confirm dialog
// =============================================================================

// ---------- EmptyState ----------
function EdEmptyState({ kicker = "NO DATA", title = "—— NOTHING HERE YET ——", body, action }) {
  return (
    <div style={{
      padding: "60px 32px",
      textAlign: "center",
      border: "1px dashed var(--line-3)",
      background: "repeating-linear-gradient(135deg, transparent, transparent 12px, rgba(255,255,255,0.012) 12px, rgba(255,255,255,0.012) 13px)",
    }}>
      <div style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-3)", letterSpacing: 2, marginBottom: 14 }}>{kicker}</div>
      <div style={{ fontFamily: "var(--f-display)", fontSize: 22, fontWeight: 700, letterSpacing: -0.3, color: "var(--fg-2)" }}>{title}</div>
      {body && <div style={{ fontFamily: "var(--f-mono)", fontSize: 11, color: "var(--fg-3)", marginTop: 10, letterSpacing: 0.5, maxWidth: 480, marginLeft: "auto", marginRight: "auto", lineHeight: 1.7 }}>{body}</div>}
      {action && <div style={{ marginTop: 22 }}>{action}</div>}
    </div>
  );
}

// ---------- Skeleton row (loading list) ----------
function EdSkeleton({ rows = 5, height = 36, gap = 10 }) {
  return (
    <div style={{ display: "grid", gap }}>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} style={{
          height,
          background: "linear-gradient(90deg, var(--bg-2) 0%, var(--bg-3) 50%, var(--bg-2) 100%)",
          backgroundSize: "200% 100%",
          animation: "edPulse 1.6s ease-in-out infinite",
          opacity: 1 - i * 0.08,
          borderLeft: i === 0 ? "2px solid var(--hot)" : "2px solid transparent",
        }}></div>
      ))}
      <style>{`@keyframes edPulse { 0%{background-position:200% 0} 100%{background-position:-200% 0} }`}</style>
    </div>
  );
}

// ---------- Toast system ----------
const ToastCtx = React.createContext(null);
function useToast() { return React.useContext(ToastCtx); }

function ToastProvider({ children }) {
  const [toasts, setToasts] = React.useState([]);
  const push = React.useCallback((t) => {
    const id = Math.random().toString(36).slice(2);
    const toast = { id, kind: "info", duration: 3500, ...t };
    setToasts((arr) => [...arr, toast]);
    if (toast.duration > 0) {
      setTimeout(() => setToasts((arr) => arr.filter((x) => x.id !== id)), toast.duration);
    }
    return id;
  }, []);
  const dismiss = React.useCallback((id) => setToasts((arr) => arr.filter((x) => x.id !== id)), []);
  const api = React.useMemo(() => ({
    push, dismiss,
    info:    (title, body) => push({ kind: "info",    title, body }),
    success: (title, body) => push({ kind: "success", title, body }),
    warn:    (title, body) => push({ kind: "warn",    title, body }),
    error:   (title, body) => push({ kind: "error",   title, body, duration: 5000 }),
  }), [push, dismiss]);
  return (
    <ToastCtx.Provider value={api}>
      {children}
      <ToastStack toasts={toasts} dismiss={dismiss} />
    </ToastCtx.Provider>
  );
}

function ToastStack({ toasts, dismiss }) {
  return (
    <div style={{
      position: "fixed", top: 18, right: 18, zIndex: 9999,
      display: "grid", gap: 8, width: 340,
      pointerEvents: "none",
    }}>
      {toasts.map((t) => <ToastCard key={t.id} t={t} onClose={() => dismiss(t.id)} />)}
    </div>
  );
}

function ToastCard({ t, onClose }) {
  const colors = {
    info:    { c: "var(--cool)", k: "INFO" },
    success: { c: "var(--good)", k: "OK"   },
    warn:    { c: "var(--warn)", k: "WARN" },
    error:   { c: "var(--bad)",  k: "ERR"  },
  }[t.kind];
  return (
    <div style={{
      pointerEvents: "auto",
      background: "var(--bg-1)",
      border: "1px solid var(--line-3)",
      borderLeft: `3px solid ${colors.c}`,
      padding: "12px 14px",
      display: "grid", gridTemplateColumns: "auto 1fr auto", gap: 10, alignItems: "start",
      animation: "edToastIn .22s ease-out both",
      fontFamily: "var(--f-body)",
    }}>
      <span style={{ fontFamily: "var(--f-mono)", fontSize: 9, color: colors.c, letterSpacing: 1.5, fontWeight: 700, marginTop: 2 }}>● {colors.k}</span>
      <div>
        <div style={{ fontFamily: "var(--f-display)", fontSize: 13, fontWeight: 700, color: "var(--fg-0)", letterSpacing: -0.1 }}>{t.title}</div>
        {t.body && <div style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", marginTop: 3, lineHeight: 1.5 }}>{t.body}</div>}
      </div>
      <button onClick={onClose} style={{ background: "none", border: "none", color: "var(--fg-3)", cursor: "pointer", fontSize: 14, padding: 0, lineHeight: 1 }}>✕</button>
      <style>{`@keyframes edToastIn { from{opacity:0;transform:translateX(20px)} to{opacity:1;transform:translateX(0)} }`}</style>
    </div>
  );
}

// ---------- Confirm dialog ----------
const ConfirmCtx = React.createContext(null);
function useConfirm() { return React.useContext(ConfirmCtx); }

function ConfirmProvider({ children }) {
  const [state, setState] = React.useState(null);
  const ask = React.useCallback((opts) => {
    return new Promise((resolve) => {
      setState({ ...opts, resolve });
    });
  }, []);
  const close = (val) => {
    if (state) state.resolve(val);
    setState(null);
  };
  return (
    <ConfirmCtx.Provider value={ask}>
      {children}
      {state && <ConfirmDialog state={state} onClose={close} />}
    </ConfirmCtx.Provider>
  );
}

function ConfirmDialog({ state, onClose }) {
  const destructive = state.destructive !== false;
  return (
    <div style={{
      position: "fixed", inset: 0, zIndex: 10000,
      background: "rgba(7,8,9,0.78)", backdropFilter: "blur(4px)",
      display: "flex", alignItems: "center", justifyContent: "center",
      animation: "edFadeIn .15s ease-out",
    }} onClick={() => onClose(false)}>
      <div onClick={(e) => e.stopPropagation()} style={{
        width: 520, background: "var(--bg-1)", border: "1px solid var(--line-3)",
        boxShadow: "0 30px 80px rgba(0,0,0,0.6)",
        animation: "edDialogIn .2s ease-out",
      }}>
        <div style={{ borderBottom: `2px solid ${destructive ? "var(--bad)" : "var(--hot)"}`, padding: "14px 22px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: destructive ? "var(--bad)" : "var(--hot)", letterSpacing: 2, fontWeight: 700 }}>
            {destructive ? "⚠ DESTRUCTIVE ACTION" : "CONFIRM"}
          </div>
          <button onClick={() => onClose(false)} style={{ background: "none", border: "none", color: "var(--fg-3)", cursor: "pointer", fontSize: 14 }}>✕</button>
        </div>
        <div style={{ padding: "26px 22px" }}>
          <div style={{ fontFamily: "var(--f-display)", fontSize: 22, fontWeight: 700, letterSpacing: -0.3, lineHeight: 1.2 }}>{state.title || "정말 진행하시겠어요?"}</div>
          {state.body && <div style={{ fontFamily: "var(--f-body)", fontSize: 13, color: "var(--fg-2)", marginTop: 10, lineHeight: 1.6 }}>{state.body}</div>}
          {state.detail && (
            <div style={{ marginTop: 16, padding: "10px 14px", background: "var(--bg-2)", border: "1px solid var(--line-2)", fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", letterSpacing: 0.5, lineHeight: 1.6 }}>
              {state.detail}
            </div>
          )}
        </div>
        <div style={{ borderTop: "1px solid var(--line-2)", padding: "12px 22px", display: "flex", gap: 8, justifyContent: "flex-end" }}>
          <button className="cv-btn ghost" onClick={() => onClose(false)} style={{ height: 34, padding: "0 16px" }}>{state.cancelText || "CANCEL"}</button>
          <button onClick={() => onClose(true)} style={{
            height: 34, padding: "0 18px",
            background: destructive ? "var(--bad)" : "var(--hot)",
            color: "#0A0B0D", border: "none", fontFamily: "var(--f-mono)", fontSize: 11, fontWeight: 700, letterSpacing: 1, cursor: "pointer",
          }}>{state.confirmText || (destructive ? "DELETE" : "CONFIRM")}</button>
        </div>
      </div>
      <style>{`
        @keyframes edFadeIn { from{opacity:0} to{opacity:1} }
        @keyframes edDialogIn { from{opacity:0;transform:translateY(8px) scale(.98)} to{opacity:1;transform:none} }
      `}</style>
    </div>
  );
}

// ---------- ON AIR badge (B5) ----------
function EdOnAir({ size = "md" }) {
  const sz = size === "sm" ? { p: "3px 8px", f: 9, dot: 6 } : size === "lg" ? { p: "8px 14px", f: 13, dot: 10 } : { p: "5px 10px", f: 11, dot: 8 };
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 8,
      padding: sz.p, fontFamily: "var(--f-mono)", fontSize: sz.f, fontWeight: 800, letterSpacing: 2,
      background: "var(--bad)", color: "#0A0B0D",
      animation: "edOnairPulse 1.4s ease-in-out infinite",
    }}>
      <span style={{
        width: sz.dot, height: sz.dot, borderRadius: "50%",
        background: "#0A0B0D", animation: "edOnairDot 0.9s ease-in-out infinite",
      }}></span>
      ON AIR
      <style>{`
        @keyframes edOnairPulse { 0%,100%{box-shadow:0 0 0 0 rgba(255,71,87,0.55)} 50%{box-shadow:0 0 0 10px rgba(255,71,87,0)} }
        @keyframes edOnairDot { 0%,100%{opacity:1} 50%{opacity:.25} }
      `}</style>
    </span>
  );
}

Object.assign(window, {
  EdEmptyState, EdSkeleton,
  ToastProvider, useToast,
  ConfirmProvider, useConfirm,
  EdOnAir,
});
