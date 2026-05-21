// Scoreboard, Login screens — broadcast-grade
function CvScoreboardScreen() {
  return (
    <div style={{ background: "#000", color: "#fff", height: "100%", display: "flex", flexDirection: "column", overflow: "hidden", position: "relative" }}>
      {/* Subtle court geometry overlay */}
      <div style={{ position: "absolute", inset: 0, pointerEvents: "none",
        background: `repeating-linear-gradient(115deg, transparent 0 80px, rgba(255,90,31,0.025) 80px 82px)` }}></div>
      <div style={{ position: "absolute", inset: 0, pointerEvents: "none", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <div style={{ width: 800, height: 800, border: "1px solid rgba(255,90,31,0.08)", borderRadius: "50%" }}></div>
      </div>

      {/* Top header */}
      <div style={{ height: 60, display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 40px",
                    borderBottom: "1px solid rgba(255,255,255,0.08)", position: "relative", zIndex: 1 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <span style={{ fontFamily: "var(--f-display)", fontSize: 18, fontWeight: 700, letterSpacing: 1 }}>
            COURT<span style={{ color: "var(--hot)" }}>VIEW</span>
          </span>
          <span style={{ width: 1, height: 20, background: "rgba(255,255,255,0.15)" }}></span>
          <span style={{ fontFamily: "var(--f-mono)", fontSize: 11, color: "var(--fg-2)", letterSpacing: 1 }}>SMC-26 · SEMIFINAL · OLYMPIC PARK</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 14, fontFamily: "var(--f-mono)", fontSize: 11, color: "var(--fg-1)" }}>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 8, padding: "5px 12px", border: "1.5px solid var(--bad)", color: "var(--bad)", fontFamily: "var(--f-display)", fontSize: 11, fontWeight: 700, letterSpacing: 2.5 }}>
            <span style={{ width: 7, height: 7, background: "var(--bad)", borderRadius: "50%", animation: "cv-onair-pulse 1.4s ease-in-out infinite" }}></span>
            ON AIR
          </span>
          <span style={{ color: "var(--fg-3)" }}>|</span>
          <span>4K · 60FPS</span>
          <span style={{ color: "var(--fg-3)" }}>|</span>
          <span>21:34:08</span>
        </div>
      </div>

      {/* Big scoreboard */}
      <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", position: "relative", zIndex: 1 }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr auto 1fr", gap: 80, alignItems: "center", padding: "0 80px", maxWidth: 1700, width: "100%" }}>
          <div style={{ textAlign: "center" }}>
            <div style={{ fontFamily: "var(--f-mono)", fontSize: 14, color: "var(--fg-2)", letterSpacing: 3, marginBottom: 12 }}>HOME · 3-0</div>
            <div style={{ fontFamily: "var(--f-display)", fontSize: 80, fontWeight: 700, letterSpacing: -2, color: "var(--hot)" }}>VOLTS</div>
            <div style={{ fontFamily: "var(--f-display)", fontSize: 320, fontWeight: 700, lineHeight: 0.85, color: "#fff", letterSpacing: -14 }}>41</div>
            <div style={{ fontFamily: "var(--f-mono)", fontSize: 14, color: "var(--fg-1)", letterSpacing: 2, marginTop: 8 }}>FOULS 8 · TO 7</div>
          </div>
          <div style={{ textAlign: "center" }}>
            <div style={{ fontFamily: "var(--f-mono)", fontSize: 16, color: "var(--fg-2)", letterSpacing: 3 }}>QUARTER</div>
            <div style={{ fontFamily: "var(--f-display)", fontSize: 130, fontWeight: 700, color: "var(--hot)", lineHeight: 1 }}>Q3</div>
            <div style={{ fontFamily: "var(--f-mono)", fontSize: 80, fontWeight: 700, color: "var(--warn)", letterSpacing: -2, marginTop: 12, lineHeight: 1 }}>07:24</div>
            <div style={{ fontFamily: "var(--f-mono)", fontSize: 14, color: "var(--fg-2)", letterSpacing: 2, marginTop: 18 }}>SHOT CLOCK</div>
            <div style={{ fontFamily: "var(--f-mono)", fontSize: 64, fontWeight: 700, color: "var(--bad)", letterSpacing: -1, lineHeight: 1, marginTop: 4 }}>14</div>
          </div>
          <div style={{ textAlign: "center" }}>
            <div style={{ fontFamily: "var(--f-mono)", fontSize: 14, color: "var(--fg-2)", letterSpacing: 3, marginBottom: 12 }}>AWAY · 2-2</div>
            <div style={{ fontFamily: "var(--f-display)", fontSize: 80, fontWeight: 700, letterSpacing: -2, color: "var(--cool)" }}>BLAZERS</div>
            <div style={{ fontFamily: "var(--f-display)", fontSize: 320, fontWeight: 700, lineHeight: 0.85, color: "#fff", letterSpacing: -14 }}>38</div>
            <div style={{ fontFamily: "var(--f-mono)", fontSize: 14, color: "var(--fg-1)", letterSpacing: 2, marginTop: 8 }}>FOULS 11 · TO 9</div>
          </div>
        </div>
      </div>

      {/* Bottom — quarter strip */}
      <div style={{ display: "grid", gridTemplateColumns: "200px repeat(4, 1fr) 200px", borderTop: "1px solid rgba(255,255,255,0.08)", position: "relative", zIndex: 1 }}>
        {["TEAM", "Q1", "Q2", "Q3", "Q4", "TOTAL"].map((h, i) => (
          <div key={i} style={{ padding: "10px 20px", borderRight: i < 5 ? "1px solid rgba(255,255,255,0.06)" : "none",
                                fontFamily: "var(--f-mono)", fontSize: 11, color: "var(--fg-2)", letterSpacing: 2, textAlign: i === 0 ? "left" : "center" }}>{h}</div>
        ))}
        {[["VOLTS", 18, 12, 11, "—", 41, "var(--hot)"], ["BLAZERS", 14, 13, 11, "—", 38, "var(--cool)"]].map((row, ri) =>
          row.map((c, ci) => (
            <div key={`${ri}-${ci}`} style={{
              padding: "16px 20px", borderTop: "1px solid rgba(255,255,255,0.06)",
              borderRight: ci < 5 ? "1px solid rgba(255,255,255,0.06)" : "none",
              textAlign: ci === 0 ? "left" : "center",
              fontFamily: ci === 0 ? "var(--f-display)" : "var(--f-mono)",
              fontWeight: ci === 0 ? 700 : ci === 5 ? 700 : 500,
              fontSize: ci === 0 ? 22 : ci === 5 ? 26 : 18,
              color: ci === 0 ? row[6] : "#fff"
            }}>{c}</div>
          ))
        )}
      </div>
    </div>
  );
}

function CvLoginScreen() {
  return (
    <div style={{ background: "var(--bg-0)", height: "100%", display: "flex", overflow: "hidden", position: "relative" }}>
      {/* Left — branding panel */}
      <div style={{ flex: 1, padding: "60px 56px", display: "flex", flexDirection: "column", justifyContent: "space-between", borderRight: "1px solid var(--line-2)", position: "relative", overflow: "hidden" }}>
        <div style={{ position: "absolute", inset: 0, pointerEvents: "none",
          background: `repeating-linear-gradient(115deg, transparent 0 50px, rgba(255,90,31,0.03) 50px 51px)` }}></div>
        <div style={{ position: "relative" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span style={{ width: 14, height: 14, border: "1.5px solid var(--hot)", borderRadius: "50%", display: "inline-block", position: "relative" }}></span>
            <span style={{ fontFamily: "var(--f-display)", fontSize: 14, fontWeight: 700, letterSpacing: 1 }}>
              COURT<span style={{ color: "var(--hot)" }}>VIEW</span>
              <sup style={{ fontSize: 8, color: "var(--fg-3)", marginLeft: 4 }}>®</sup>
            </span>
          </div>
        </div>
        <div style={{ position: "relative" }}>
          <div style={{ fontFamily: "var(--f-mono)", fontSize: 11, color: "var(--hot)", letterSpacing: 2, marginBottom: 12 }}>v2.4.0 · BUILD 28194</div>
          <h1 style={{ fontFamily: "var(--f-display)", fontSize: 76, fontWeight: 700, letterSpacing: -2, lineHeight: 0.92 }}>
            BASKETBALL<br />
            <span style={{ color: "var(--hot)" }}>OPERATIONS</span><br />
            DECODED.
          </h1>
          <p style={{ fontFamily: "var(--f-mono)", fontSize: 12, color: "var(--fg-2)", marginTop: 22, maxWidth: 440, lineHeight: 1.7 }}>
            REAL-TIME MULTI-CAMERA TRACKING · PLAYER ANALYTICS<br />
            BROADCAST-GRADE SCOREBOARD · LICENSED FOR FIBA / KBL / NBL
          </p>
        </div>
        <div style={{ position: "relative", display: "flex", gap: 24, fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-3)", letterSpacing: 1.2 }}>
          <span>SPOIN INC.</span><span>·</span>
          <span>SEOUL · KR</span><span>·</span>
          <span>EST 2024</span>
        </div>
      </div>

      {/* Right — login form */}
      <div style={{ width: 460, display: "flex", flexDirection: "column", justifyContent: "center", padding: "0 48px", background: "var(--bg-1)" }}>
        <div style={{ fontFamily: "var(--f-mono)", fontSize: 11, color: "var(--fg-2)", letterSpacing: 2 }}>SECURE LOGIN · 002</div>
        <h2 style={{ fontFamily: "var(--f-display)", fontSize: 36, fontWeight: 700, letterSpacing: -1, marginTop: 8 }}>OPERATOR<br />ACCESS</h2>

        <div style={{ marginTop: 28 }}>
          <label style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", letterSpacing: 1.5 }}>EMAIL</label>
          <input defaultValue="operator@spoin.kr" style={inputSt} />
        </div>
        <div style={{ marginTop: 14 }}>
          <label style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", letterSpacing: 1.5 }}>PASSWORD</label>
          <input type="password" defaultValue="••••••••••" style={inputSt} />
        </div>

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 14, fontFamily: "var(--f-mono)", fontSize: 11, color: "var(--fg-2)" }}>
          <label style={{ display: "flex", gap: 6, alignItems: "center", cursor: "pointer" }}>
            <input type="checkbox" defaultChecked /> KEEP SIGNED IN
          </label>
          <a style={{ color: "var(--hot)" }} href="#">FORGOT?</a>
        </div>

        <button className="cv-btn primary" style={{ width: "100%", marginTop: 22, height: 44, fontSize: 12, letterSpacing: 1.5 }}>
          AUTHENTICATE → 
        </button>
        <button className="cv-btn ghost" style={{ width: "100%", marginTop: 8, height: 38, fontSize: 11, letterSpacing: 1.2 }}>
          USE LICENSE KEY
        </button>

        <div style={{ marginTop: 34, paddingTop: 20, borderTop: "1px solid var(--line-2)", fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-3)", letterSpacing: 0.8 }}>
          © 2026 SPOIN INC. · ALL RIGHTS RESERVED
        </div>
      </div>
    </div>
  );
}

const inputSt = {
  width: "100%", marginTop: 6, padding: "12px 14px",
  background: "var(--bg-2)", border: "1px solid var(--line-2)",
  fontFamily: "var(--f-mono)", fontSize: 13, color: "var(--fg-0)",
  outline: "none", borderRadius: 0
};

window.CvScoreboardScreen = CvScoreboardScreen;
window.CvLoginScreen = CvLoginScreen;
