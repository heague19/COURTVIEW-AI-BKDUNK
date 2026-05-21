// =============================================================================
// COURTVIEW — COMPARISON MODE (C8)
// Side-by-side player comparison. Editorial visual skin.
// =============================================================================

function CvComparisonScreen() {
  // Two roster choices — these would come from a route param / select in production
  const players = [
    { num: 11, name: "K. PARK",  team: "FALCONS", teamColor: "var(--hot)",  pos: "PG", ht: 188, age: 26, country: "KR",
      season: { gp: 24, mpg: 33.1, ppg: 24.3, rpg: 5.2, apg: 6.8, spg: 1.7, bpg: 0.4, fgp: 49.1, tpp: 41.2, ftp: 86.4, ts: 61.4, efg: 56.8, eff: 28.1, pm: "+8.4" },
      last5pts: [22, 28, 19, 31, 26], shotZones: { paint: 64, mid: 38, three: 41 },
      strengths: ["clutch shooting", "elite court vision", "low TO rate"],
      weaknesses: ["defensive rebounding", "post scoring"],
    },
    { num: 23, name: "M. HAN",   team: "TITANS",  teamColor: "var(--cool)", pos: "C",  ht: 207, age: 28, country: "KR",
      season: { gp: 22, mpg: 31.2, ppg: 19.8, rpg: 11.6, apg: 2.1, spg: 0.7, bpg: 2.4, fgp: 56.3, tpp: 0,    ftp: 71.2, ts: 58.1, efg: 56.3, eff: 26.4, pm: "+5.1" },
      last5pts: [16, 22, 18, 24, 20], shotZones: { paint: 71, mid: 32, three: 0 },
      strengths: ["rim protection", "offensive rebounds", "post finishing"],
      weaknesses: ["free-throw consistency", "perimeter mobility"],
    },
  ];

  return (
    <div style={{ background: "var(--bg-1)", color: "var(--fg-0)", height: "100%", display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <TopNav active="result" />
      <div style={{ flex: 1, overflow: "auto" }}>
        {/* Back nav */}
        <div style={{ padding: "16px 48px 0", display: "flex", alignItems: "center", gap: 14 }}>
          <a href="#result" style={{ fontFamily: "var(--f-mono)", fontSize: 11, color: "var(--fg-2)", letterSpacing: 1, textDecoration: "none", borderBottom: "1px solid var(--line-3)", paddingBottom: 2 }}>← BACK</a>
          <span style={{ flex: 1, height: 1, background: "var(--line-2)" }}></span>
          <span style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-3)", letterSpacing: 1.5 }}>COMPARE · 2025–26 SEASON</span>
        </div>

        {/* Hero — minimal, names face off */}
        <div style={{ padding: "32px 48px 28px", borderBottom: "1px solid var(--line-2)" }}>
          <div style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", letterSpacing: 2, marginBottom: 14 }}>HEAD-TO-HEAD · PLAYER COMPARISON</div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr auto 1fr", alignItems: "stretch", gap: 32 }}>
            {/* Left player */}
            <PlayerHeroCard p={players[0]} side="left" />
            {/* VS */}
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 12 }}>
              <div style={{ fontFamily: "var(--f-display)", fontSize: 64, fontWeight: 800, color: "var(--fg-3)", letterSpacing: -3, lineHeight: 1 }}>VS</div>
              <div style={{ width: 1, height: 80, background: "var(--line-2)" }}></div>
              <div style={{ fontFamily: "var(--f-mono)", fontSize: 9, color: "var(--fg-3)", letterSpacing: 1.5, textAlign: "center", maxWidth: 60, lineHeight: 1.5 }}>SEASON AVG</div>
            </div>
            {/* Right player */}
            <PlayerHeroCard p={players[1]} side="right" />
          </div>
        </div>

        {/* Stat comparison rows — visual diverging bars */}
        <EdPanel kicker="01 · STATISTICAL COMPARISON" title="시즌 평균 — 분야별 비교" padding="28px 48px">
          <div style={{ display: "grid", gap: 4 }}>
            {[
              { k: "POINTS",       hk: "ppg", min: 0, max: 30, format: v => v.toFixed(1) },
              { k: "REBOUNDS",     hk: "rpg", min: 0, max: 14, format: v => v.toFixed(1) },
              { k: "ASSISTS",      hk: "apg", min: 0, max: 10, format: v => v.toFixed(1) },
              { k: "STEALS",       hk: "spg", min: 0, max: 3,  format: v => v.toFixed(1) },
              { k: "BLOCKS",       hk: "bpg", min: 0, max: 3,  format: v => v.toFixed(1) },
              { k: "FG%",          hk: "fgp", min: 30, max: 65, format: v => `${v}%` },
              { k: "3P%",          hk: "tpp", min: 0,  max: 50, format: v => `${v}%` },
              { k: "FT%",          hk: "ftp", min: 50, max: 95, format: v => `${v}%` },
              { k: "TS%",          hk: "ts",  min: 40, max: 70, format: v => `${v}%` },
              { k: "EFG%",         hk: "efg", min: 40, max: 65, format: v => `${v}%` },
              { k: "EFFICIENCY",   hk: "eff", min: 10, max: 35, format: v => v.toFixed(1) },
              { k: "PLUS / MINUS", hk: "pm",  min: -10, max: 15, format: v => v, plain: true },
            ].map((row, i) => (
              <CompareBar key={i} row={row} a={players[0]} b={players[1]} />
            ))}
          </div>
        </EdPanel>

        {/* Last 5 + shot zones */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 1, background: "var(--line-2)" }}>
          {/* Left — last 5 games trajectory */}
          <EdPanel kicker="02 · LAST 5 GAMES" title="최근 5경기 득점 추이">
            <Last5Compare a={players[0]} b={players[1]} />
          </EdPanel>

          {/* Right — shot zones radar/bars */}
          <EdPanel kicker="03 · SHOT DISTRIBUTION" title="존별 효율성">
            <ZoneCompare a={players[0]} b={players[1]} />
          </EdPanel>
        </div>

        {/* Qualitative — strengths / weaknesses */}
        <EdPanel kicker="04 · SCOUT REPORT" title="강점 · 약점" padding="28px 48px">
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 32 }}>
            {players.map((p, i) => (
              <div key={i} style={{ borderTop: `2px solid ${p.teamColor}`, paddingTop: 14 }}>
                <div style={{ fontFamily: "var(--f-display)", fontSize: 18, fontWeight: 700, color: p.teamColor, letterSpacing: -0.3, marginBottom: 16 }}>{p.name}</div>
                <div style={{ marginBottom: 18 }}>
                  <div style={{ fontFamily: "var(--f-mono)", fontSize: 9, color: "var(--good)", letterSpacing: 1.5, marginBottom: 8 }}>● STRENGTHS</div>
                  {p.strengths.map((s, j) => (
                    <div key={j} style={{ display: "flex", gap: 12, padding: "8px 0", borderBottom: "1px solid var(--line-1)", fontFamily: "var(--f-display)", fontSize: 14, fontWeight: 500 }}>
                      <span style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-3)", width: 24, paddingTop: 2 }}>0{j+1}</span>
                      <span>{s}</span>
                    </div>
                  ))}
                </div>
                <div>
                  <div style={{ fontFamily: "var(--f-mono)", fontSize: 9, color: "var(--bad)", letterSpacing: 1.5, marginBottom: 8 }}>○ WEAKNESSES</div>
                  {p.weaknesses.map((s, j) => (
                    <div key={j} style={{ display: "flex", gap: 12, padding: "8px 0", borderBottom: "1px solid var(--line-1)", fontFamily: "var(--f-display)", fontSize: 14, fontWeight: 500, color: "var(--fg-2)" }}>
                      <span style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-3)", width: 24, paddingTop: 2 }}>0{j+1}</span>
                      <span>{s}</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </EdPanel>

        {/* Footer actions */}
        <div style={{ padding: "24px 48px 48px", display: "flex", gap: 8, borderTop: "1px solid var(--line-2)" }}>
          <button className="cv-btn primary" style={{ height: 36 }}>↓ EXPORT REPORT</button>
          <button className="cv-btn" style={{ height: 36 }}>+ ADD PLAYER</button>
          <button className="cv-btn" style={{ height: 36 }}>↻ SWAP MATCHUP</button>
          <span style={{ flex: 1 }}></span>
          <span style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-3)", letterSpacing: 1, alignSelf: "center" }}>DATA · 2025-26 REGULAR SEASON · UPDATED 21:34</span>
        </div>
      </div>
    </div>
  );
}

function PlayerHeroCard({ p, side }) {
  const initials = p.name.split(/[ .]+/).filter(Boolean).slice(0, 2).map(x => x[0]).join("");
  const align = side === "right" ? "left" : "right";
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14, alignItems: align === "right" ? "flex-end" : "flex-start", textAlign: align }}>
      <div style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-3)", letterSpacing: 2 }}>
        {p.team} · #{p.num} · {p.pos}
      </div>
      <div style={{ display: "flex", gap: 18, alignItems: "center", flexDirection: side === "right" ? "row-reverse" : "row" }}>
        <div style={{
          width: 96, height: 124,
          background: `linear-gradient(165deg, ${p.teamColor}66, ${p.teamColor}11 60%, var(--bg-3))`,
          border: `1px solid ${p.teamColor}`,
          display: "flex", alignItems: "flex-end", justifyContent: "center",
          fontFamily: "var(--f-display)", fontSize: 44, fontWeight: 700, color: "rgba(255,255,255,0.95)",
          letterSpacing: -2, paddingBottom: 8, position: "relative", overflow: "hidden",
        }}>
          <span style={{ position: "absolute", top: 8, left: side === "left" ? 8 : "auto", right: side === "right" ? 8 : "auto", fontFamily: "var(--f-mono)", fontSize: 10, color: p.teamColor, letterSpacing: 1 }}>#{p.num}</span>
          {initials}
        </div>
        <div>
          <div style={{ fontFamily: "var(--f-display)", fontSize: 44, fontWeight: 800, color: p.teamColor, letterSpacing: -1.5, lineHeight: 1 }}>{p.name}</div>
          <div style={{ fontFamily: "var(--f-mono)", fontSize: 11, color: "var(--fg-2)", marginTop: 6, letterSpacing: 1 }}>{p.ht} CM · {p.age} YR · {p.country}</div>
          <div style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-3)", marginTop: 4, letterSpacing: 1 }}>{p.season.gp} GAMES · {p.season.mpg} MPG</div>
        </div>
      </div>
    </div>
  );
}

function CompareBar({ row, a, b }) {
  const va = +a.season[row.hk] || 0;
  const vb = +b.season[row.hk] || 0;
  const winner = va > vb ? "a" : vb > va ? "b" : null;
  const range = row.max - row.min;
  const aPct = Math.min(100, Math.max(0, ((va - row.min) / range) * 100));
  const bPct = Math.min(100, Math.max(0, ((vb - row.min) / range) * 100));

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 90px 220px 90px 1fr", gap: 12, alignItems: "center", padding: "10px 0", borderBottom: "1px solid var(--line-1)" }}>
      {/* A bar (right-anchored) */}
      <div style={{ display: "flex", justifyContent: "flex-end", alignItems: "center" }}>
        <div style={{ width: "100%", height: 8, background: "var(--bg-2)", border: "1px solid var(--line-2)", position: "relative", overflow: "hidden" }}>
          <div style={{ position: "absolute", right: 0, top: 0, bottom: 0, width: `${aPct}%`, background: a.teamColor, opacity: winner === "a" ? 1 : 0.5 }}></div>
        </div>
      </div>
      <div style={{ fontFamily: "var(--f-display)", fontSize: 22, fontWeight: 700, color: winner === "a" ? a.teamColor : "var(--fg-2)", textAlign: "right", letterSpacing: -0.5, fontVariantNumeric: "tabular-nums" }}>
        {row.format(va)}
      </div>
      {/* Label */}
      <div style={{ textAlign: "center" }}>
        <div style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-3)", letterSpacing: 1.5 }}>{row.k}</div>
        {winner && (
          <div style={{ fontFamily: "var(--f-mono)", fontSize: 9, color: "var(--good)", letterSpacing: 1, marginTop: 2 }}>
            ◀ +{Math.abs(va - vb).toFixed(row.k.includes("%") || row.hk === "eff" ? 1 : 1)} {winner === "a" ? "" : "▶"}
            {winner === "b" && <span>{""}</span>}
          </div>
        )}
      </div>
      {/* B value */}
      <div style={{ fontFamily: "var(--f-display)", fontSize: 22, fontWeight: 700, color: winner === "b" ? b.teamColor : "var(--fg-2)", textAlign: "left", letterSpacing: -0.5, fontVariantNumeric: "tabular-nums" }}>
        {row.format(vb)}
      </div>
      {/* B bar (left-anchored) */}
      <div style={{ display: "flex", justifyContent: "flex-start", alignItems: "center" }}>
        <div style={{ width: "100%", height: 8, background: "var(--bg-2)", border: "1px solid var(--line-2)", position: "relative", overflow: "hidden" }}>
          <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: `${bPct}%`, background: b.teamColor, opacity: winner === "b" ? 1 : 0.5 }}></div>
        </div>
      </div>
    </div>
  );
}

function Last5Compare({ a, b }) {
  const max = Math.max(...a.last5pts, ...b.last5pts);
  return (
    <div style={{ padding: "8px 0" }}>
      <div style={{ display: "grid", gridTemplateColumns: "60px 1fr", gap: 14, alignItems: "center" }}>
        <div style={{ fontFamily: "var(--f-display)", fontSize: 13, fontWeight: 700, color: a.teamColor }}>{a.name.split(" ")[1] || a.name}</div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 6, height: 60, alignItems: "end" }}>
          {a.last5pts.map((v, i) => (
            <div key={i} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
              <span style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", fontWeight: 600 }}>{v}</span>
              <div style={{ width: "100%", height: `${(v/max)*40}px`, background: a.teamColor, opacity: 0.85 }}></div>
            </div>
          ))}
        </div>
      </div>
      <div style={{ height: 1, background: "var(--line-2)", margin: "16px 0" }}></div>
      <div style={{ display: "grid", gridTemplateColumns: "60px 1fr", gap: 14, alignItems: "center" }}>
        <div style={{ fontFamily: "var(--f-display)", fontSize: 13, fontWeight: 700, color: b.teamColor }}>{b.name.split(" ")[1] || b.name}</div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 6, height: 60, alignItems: "end" }}>
          {b.last5pts.map((v, i) => (
            <div key={i} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
              <span style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", fontWeight: 600 }}>{v}</span>
              <div style={{ width: "100%", height: `${(v/max)*40}px`, background: b.teamColor, opacity: 0.85 }}></div>
            </div>
          ))}
        </div>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "60px repeat(5, 1fr)", gap: 6, marginTop: 10, paddingTop: 10, borderTop: "1px solid var(--line-2)" }}>
        <div></div>
        {["G-5", "G-4", "G-3", "G-2", "LAST"].map(g => (
          <div key={g} style={{ fontFamily: "var(--f-mono)", fontSize: 9, color: "var(--fg-3)", letterSpacing: 1, textAlign: "center" }}>{g}</div>
        ))}
      </div>
    </div>
  );
}

function ZoneCompare({ a, b }) {
  const zones = [
    { k: "PAINT",     ak: "paint" },
    { k: "MID-RANGE", ak: "mid" },
    { k: "3-POINT",   ak: "three" },
  ];
  return (
    <div style={{ padding: "8px 0" }}>
      {zones.map((z, i) => {
        const va = a.shotZones[z.ak];
        const vb = b.shotZones[z.ak];
        return (
          <div key={i} style={{ marginBottom: 16, paddingBottom: 14, borderBottom: i < zones.length - 1 ? "1px solid var(--line-1)" : "none" }}>
            <div style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", letterSpacing: 1.5, marginBottom: 8 }}>{z.k} · FG%</div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 50px", gap: 10, alignItems: "center", marginBottom: 6 }}>
              <div style={{ height: 12, background: "var(--bg-2)", border: "1px solid var(--line-2)", position: "relative" }}>
                <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: `${va}%`, background: a.teamColor }}></div>
              </div>
              <div style={{ fontFamily: "var(--f-display)", fontSize: 14, fontWeight: 700, color: a.teamColor, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{va}%</div>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 50px", gap: 10, alignItems: "center" }}>
              <div style={{ height: 12, background: "var(--bg-2)", border: "1px solid var(--line-2)", position: "relative" }}>
                <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: `${vb}%`, background: b.teamColor }}></div>
              </div>
              <div style={{ fontFamily: "var(--f-display)", fontSize: 14, fontWeight: 700, color: b.teamColor, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{vb}%</div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

window.CvComparisonScreen = CvComparisonScreen;
