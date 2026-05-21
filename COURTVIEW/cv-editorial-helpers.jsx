// =============================================================================
// COURTVIEW — Editorial helpers shared by all supporting screens
// Hero bands, stat strips, rule lines — strict magazine grid.
// =============================================================================

function EdHero({ issue = "001", date = "05 · 07 · 2026", tag, tagText, kicker, title, subline, right, size = "lg" }) {
  // title can be a string OR a {primary, accent} object for two-color hero type
  const t = typeof title === "string" ? { primary: title, accent: "" } : title;
  // size variants — let secondary pages breathe smaller so primary pages feel headline
  const sz = size === "xl" ? { fs: 92, ls: -3, pt: 40 }
           : size === "lg" ? { fs: 76, ls: -2.5, pt: 36 }
           : size === "md" ? { fs: 56, ls: -1.8, pt: 32 }
           : { fs: 44, ls: -1.4, pt: 28 }; // sm
  return (
    <div style={{ padding: `${sz.pt}px 48px 26px`, borderBottom: "1px solid var(--line-2)", position: "relative" }}>
      <div style={{ position: "absolute", top: 26, right: 48, fontFamily: "var(--f-mono)", fontSize: 11, color: "var(--fg-3)", letterSpacing: 1.4, textAlign: "right" }}>
        <div>ISSUE · {issue}</div>
        <div style={{ marginTop: 4 }}>{date}</div>
      </div>
      {(tag || kicker) && (
        <div style={{ display: "flex", gap: 10, alignItems: "center", marginBottom: 12 }}>
          {tag && <span className={`cv-tag ${tag}`}>{tagText}</span>}
          {kicker && <span style={{ fontFamily: "var(--f-mono)", fontSize: 11, color: "var(--fg-2)", letterSpacing: 1 }}>{kicker}</span>}
        </div>
      )}
      <h1 style={{
        fontFamily: "var(--f-display)", fontSize: sz.fs, fontWeight: 700,
        letterSpacing: sz.ls, lineHeight: 0.92, maxWidth: 1100, marginTop: 4
      }}>
        {t.primary}{t.accent && <><br /><span style={{ color: "var(--hot)" }}>{t.accent}</span></>}
      </h1>
      {subline && (
        <div style={{ display: "flex", gap: 32, marginTop: 16, fontFamily: "var(--f-mono)", fontSize: 12, color: "var(--fg-1)", flexWrap: "wrap" }}>
          {subline.map((s, i) => (
            <span key={i}>
              <span style={{ color: "var(--fg-3)" }}>{s.k} —</span> {s.v}
            </span>
          ))}
        </div>
      )}
      {right && (
        <div style={{ position: "absolute", bottom: 26, right: 48 }}>{right}</div>
      )}
    </div>
  );
}

function EdStatStrip({ items }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: `repeat(${items.length}, 1fr)`, borderBottom: "1px solid var(--line-2)" }}>
      {items.map((it, i) => (
        <div key={i} style={{ padding: "16px 22px", borderRight: i < items.length - 1 ? "1px solid var(--line-1)" : "none" }}>
          <div style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", letterSpacing: 1.2 }}>{it.k}</div>
          <div style={{ fontFamily: "var(--f-display)", fontSize: 36, fontWeight: 700, color: it.c || "var(--fg-0)", lineHeight: 1, marginTop: 4, letterSpacing: -1 }}>{it.v}</div>
          {it.sub && <div style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-3)", marginTop: 6, letterSpacing: 1 }}>{it.sub}</div>}
        </div>
      ))}
    </div>
  );
}

function EdSectionHead({ kicker, title, sub, right }) {
  return (
    <div style={{ display: "flex", alignItems: "baseline", gap: 14, marginBottom: 14 }}>
      <div>
        {kicker && (
          <div style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", letterSpacing: 2, marginBottom: 4 }}>{kicker}</div>
        )}
        <div style={{ fontFamily: "var(--f-display)", fontSize: 24, fontWeight: 700, letterSpacing: -0.5 }}>{title}</div>
        {sub && <div style={{ fontFamily: "var(--f-mono)", fontSize: 11, color: "var(--fg-2)", marginTop: 4 }}>{sub}</div>}
      </div>
      <span style={{ flex: 1, height: 1, background: "var(--line-2)", alignSelf: "center", marginTop: 8 }}></span>
      {right}
    </div>
  );
}

function EdPanel({ children, title, kicker, right, padding = "24px 28px", style = {} }) {
  return (
    <div style={{ background: "var(--bg-1)", padding, ...style }}>
      {(title || kicker) && (
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
          <span style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", letterSpacing: 2 }}>{kicker}</span>
          {title && <span style={{ fontFamily: "var(--f-display)", fontSize: 18, fontWeight: 700, letterSpacing: -0.4 }}>{title}</span>}
          <span style={{ flex: 1, height: 1, background: "var(--line-2)" }}></span>
          {right}
        </div>
      )}
      {children}
    </div>
  );
}

// Rule-line table — all hairlines, mono headers, display values
function EdTable({ cols, rows, accentCol = -1 }) {
  // cols: [{k, w, align}]
  const tpl = cols.map(c => c.w || "1fr").join(" ");
  return (
    <div>
      <div style={{ display: "grid", gridTemplateColumns: tpl, padding: "10px 0", borderBottom: "1px solid var(--line-2)" }}>
        {cols.map((c, i) => (
          <span key={i} style={{
            fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", letterSpacing: 1.2,
            textAlign: c.align || "left", paddingRight: 8
          }}>{c.k}</span>
        ))}
      </div>
      {rows.map((row, ri) => (
        <div key={ri} style={{ display: "grid", gridTemplateColumns: tpl, padding: "12px 0", borderBottom: "1px solid var(--line-1)", alignItems: "center" }}>
          {row.map((cell, ci) => {
            const c = cols[ci] || {};
            const isAccent = ci === accentCol;
            return (
              <span key={ci} style={{
                fontFamily: c.f || (ci === 0 ? "var(--f-display)" : "var(--f-mono)"),
                fontSize: c.fs || (ci === 0 ? 14 : 12),
                fontWeight: ci === 0 ? 700 : 500,
                color: isAccent ? "var(--hot)" : (ci === 0 ? "var(--fg-0)" : "var(--fg-1)"),
                textAlign: c.align || "left",
                paddingRight: 8,
                letterSpacing: ci === 0 ? -0.2 : 0.2,
              }}>{cell}</span>
            );
          })}
        </div>
      ))}
    </div>
  );
}

// Big bordered metric — used in headers / KPI rails
function EdBigMetric({ k, v, sub, color, size = 56 }) {
  return (
    <div>
      <div style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", letterSpacing: 1.2 }}>{k}</div>
      <div style={{ fontFamily: "var(--f-display)", fontSize: size, fontWeight: 700, color: color || "var(--fg-0)", lineHeight: 0.9, marginTop: 6, letterSpacing: -1.5 }}>{v}</div>
      {sub && <div style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-3)", marginTop: 6, letterSpacing: 1 }}>{sub}</div>}
    </div>
  );
}

Object.assign(window, { EdHero, EdStatStrip, EdSectionHead, EdPanel, EdTable, EdBigMetric });
