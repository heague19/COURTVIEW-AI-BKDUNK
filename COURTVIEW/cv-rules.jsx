// =============================================================================
// COURTVIEW — Rules & competition settings
// 대회 규칙 / 로컬 룰 세팅. 프리셋 저장 + 커스텀 룰 입력.
// 학원농구 · 생활체육 · 동호회 · 3x3 등 다양한 룰셋을 한 번 정의해 두고 재사용.
// =============================================================================

function CvRulesScreen() {
  // -------- Rule presets -----------------------------------------------------
  const presets = [
    {
      id: "fiba", name: "FIBA",
      org: "International / KBL · 정식 룰",
      base: { periods: 4, length: "10:00", otLength: "05:00", shotClock: 24, resetClock: 14, bonus: 5, totalTO: 5, fouled: 5, threshold: 3.0 },
    },
    {
      id: "nba", name: "NBA",
      org: "북미 프로농구",
      base: { periods: 4, length: "12:00", otLength: "05:00", shotClock: 24, resetClock: 14, bonus: 5, totalTO: 7, fouled: 6, threshold: 3.0 },
    },
    {
      id: "khsl", name: "학원농구",
      org: "고교농구연맹 표준",
      base: { periods: 4, length: "08:00", otLength: "04:00", shotClock: 24, resetClock: 14, bonus: 5, totalTO: 4, fouled: 5, threshold: 3.0 },
    },
    {
      id: "social", name: "생활체육",
      org: "일반 동호회 · 짧은 경기",
      base: { periods: 4, length: "07:00", otLength: "03:00", shotClock: 30, resetClock: 14, bonus: 5, totalTO: 3, fouled: 5, threshold: 3.0 },
    },
    {
      id: "3x3", name: "3 × 3",
      org: "FIBA 3x3 공식",
      base: { periods: 1, length: "10:00", otLength: "—", shotClock: 12, resetClock: 12, bonus: 7, totalTO: 1, fouled: 4, threshold: 3.0 },
    },
    {
      id: "youth", name: "유소년",
      org: "초등 / 중등 단축 경기",
      base: { periods: 4, length: "06:00", otLength: "02:00", shotClock: 30, resetClock: 14, bonus: 4, totalTO: 3, fouled: 5, threshold: 2.5 },
    },
  ];

  const [activePreset, setActivePreset] = React.useState("fiba");
  const [rules, setRules] = React.useState(presets[0].base);
  const [tournamentName, setTournamentName] = React.useState("2025 강남 봄 리그");
  const [season, setSeason] = React.useState("2025 SPRING");
  const [savedAs, setSavedAs] = React.useState(null);

  // Local rules — 대회만의 추가 규정
  const [localRules, setLocalRules] = React.useState([
    { id: 1, label: "전반 한 쿼터 무실점 시 감점", on: false, value: "—" },
    { id: 2, label: "쿼터 종료 후 30초 작전타임", on: true, value: "30s" },
    { id: 3, label: "양 팀 동점 시 추가 OT 1회", on: true, value: "01:00" },
    { id: 4, label: "기술파울 자유투 1구 + 점유", on: true, value: "1FT" },
    { id: 5, label: "U파울 (비신사적) 자유투 2구 + 점유", on: true, value: "2FT" },
    { id: 6, label: "벤치 인원 제한", on: true, value: "12명" },
    { id: 7, label: "타임아웃 호출 — 코치만 가능", on: false, value: "—" },
    { id: 8, label: "비디오 챌린지 1회 / 경기", on: false, value: "—" },
  ]);

  function applyPreset(id) {
    const p = presets.find(x => x.id === id);
    if (!p) return;
    setActivePreset(id);
    setRules(p.base);
  }

  function setRule(key, val) {
    setRules(prev => ({ ...prev, [key]: val }));
  }

  function toggleLocal(id) {
    setLocalRules(prev => prev.map(r => r.id === id ? { ...r, on: !r.on } : r));
  }

  return (
    <div style={{ background: "var(--bg-1)", color: "var(--fg-0)", height: "100%", display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <TopNav active="rules" />

      {/* Editorial hero — small variant */}
      <div style={{ padding: "20px 24px 18px", borderBottom: "1px solid var(--line-2)", background: "var(--bg-0)" }}>
        <div style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-3)", letterSpacing: 2, marginBottom: 10 }}>
          07 · COMPETITION RULES
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr auto auto", alignItems: "end", gap: 24 }}>
          <h1 style={{ margin: 0, fontFamily: "var(--f-display)", fontSize: 44, fontWeight: 800, letterSpacing: -1.5, lineHeight: 1 }}>
            대회 규칙 <span style={{ color: "var(--hot)" }}>설정</span>
            <span style={{ marginLeft: 14, fontFamily: "var(--f-mono)", fontSize: 12, color: "var(--fg-3)", letterSpacing: 1, fontWeight: 400 }}>
              Tournament & local rules
            </span>
          </h1>
          <input value={tournamentName} onChange={e => setTournamentName(e.target.value)}
            style={{
              background: "transparent", border: "none", borderBottom: "1px solid var(--line-3)",
              padding: "6px 4px", color: "var(--fg-0)", fontFamily: "var(--f-display)",
              fontWeight: 700, fontSize: 18, width: 280, outline: "none", textAlign: "right",
            }} />
          <input value={season} onChange={e => setSeason(e.target.value.toUpperCase())}
            style={{
              background: "transparent", border: "none", borderBottom: "1px solid var(--line-3)",
              padding: "6px 4px", color: "var(--fg-2)", fontFamily: "var(--f-mono)",
              fontSize: 11, letterSpacing: 1.5, width: 130, outline: "none", textAlign: "right",
            }} />
        </div>
      </div>

      {/* Body */}
      <div style={{ flex: 1, display: "grid", gridTemplateColumns: "320px 1fr 360px", gap: 1, background: "var(--line-2)", overflow: "hidden", minHeight: 0 }}>

        {/* === LEFT — Preset library === */}
        <aside style={{ background: "var(--bg-1)", padding: "18px 16px", overflow: "auto", minHeight: 0 }}>
          <SectionHead num="01" label="규칙 프리셋" sub="Rule presets" />
          {presets.map((p) => {
            const active = activePreset === p.id;
            return (
              <button key={p.id} onClick={() => applyPreset(p.id)}
                style={{
                  display: "block", textAlign: "left", width: "100%", padding: "12px 14px",
                  background: active ? "var(--bg-3)" : "var(--bg-2)",
                  border: active ? "1px solid var(--hot)" : "1px solid var(--line-2)",
                  marginBottom: 6, cursor: "pointer", color: "var(--fg-0)",
                  position: "relative",
                }}>
                <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 3 }}>
                  <span style={{ fontFamily: "var(--f-display)", fontSize: 15, fontWeight: 700, letterSpacing: -0.3 }}>{p.name}</span>
                  {active && <span style={{ fontFamily: "var(--f-mono)", fontSize: 8, color: "var(--hot)", letterSpacing: 1.5 }}>● ACTIVE</span>}
                </div>
                <div style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", lineHeight: 1.45 }}>
                  {p.org}
                </div>
                <div style={{ marginTop: 6, display: "flex", gap: 8, fontFamily: "var(--f-mono)", fontSize: 9, color: "var(--fg-3)", letterSpacing: 0.5 }}>
                  <span>{p.base.periods}Q × {p.base.length}</span>
                  <span>·</span>
                  <span>{p.base.shotClock}s</span>
                  <span>·</span>
                  <span>TO {p.base.totalTO}</span>
                </div>
              </button>
            );
          })}

          <button className="cv-btn" style={{ width: "100%", marginTop: 8, height: 38, fontSize: 11 }}>
            + 새 프리셋 만들기
          </button>

          <SectionHead num="02" label="저장 / 불러오기" sub="Save & load" mt={22} />
          <div style={{ display: "grid", gap: 4 }}>
            <button className="cv-btn primary" style={{ height: 36, fontSize: 11 }}
              onClick={() => setSavedAs(`${tournamentName} · ${new Date().toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" })}`)}>
              현재 설정 저장
            </button>
            <button className="cv-btn" style={{ height: 32, fontSize: 10 }}>JSON 내보내기</button>
            <button className="cv-btn" style={{ height: 32, fontSize: 10 }}>파일에서 불러오기</button>
          </div>
          {savedAs && (
            <div style={{ marginTop: 8, padding: "8px 10px", background: "var(--bg-2)", border: "1px solid var(--good)",
                          fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--good)", lineHeight: 1.4 }}>
              ✓ 저장 완료<br />
              <span style={{ color: "var(--fg-2)" }}>{savedAs}</span>
            </div>
          )}
        </aside>

        {/* === CENTER — Standard rules grid === */}
        <main style={{ background: "var(--bg-1)", padding: "18px 24px", overflow: "auto", minHeight: 0 }}>
          <SectionHead num="03" label="기본 규정" sub="Standard rules · 시간 / 파울 / 슛 클락" />

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <RuleCard label="쿼터 수" sub="PERIODS" value={rules.periods}
              onChange={(v) => setRule("periods", parseInt(v) || 1)} type="num" min={1} max={4} unit="Q" />
            <RuleCard label="쿼터 시간" sub="PERIOD LENGTH" value={rules.length}
              onChange={(v) => setRule("length", v)} type="time" />
            <RuleCard label="연장 시간" sub="OVERTIME" value={rules.otLength}
              onChange={(v) => setRule("otLength", v)} type="time" />
            <RuleCard label="슛 클락" sub="SHOT CLOCK" value={rules.shotClock}
              onChange={(v) => setRule("shotClock", parseInt(v) || 24)} type="num" min={8} max={35} unit="s" />
            <RuleCard label="리셋 클락" sub="OFFENSIVE REBOUND" value={rules.resetClock}
              onChange={(v) => setRule("resetClock", parseInt(v) || 14)} type="num" min={8} max={24} unit="s" />
            <RuleCard label="팀 보너스 진입" sub="TEAM-FOUL BONUS" value={rules.bonus}
              onChange={(v) => setRule("bonus", parseInt(v) || 5)} type="num" min={3} max={7} unit="파울" />
            <RuleCard label="작전타임" sub="TOTAL TIMEOUTS" value={rules.totalTO}
              onChange={(v) => setRule("totalTO", parseInt(v) || 5)} type="num" min={1} max={9} unit="회" />
            <RuleCard label="개인파울 퇴장" sub="FOUL OUT" value={rules.fouled}
              onChange={(v) => setRule("fouled", parseInt(v) || 5)} type="num" min={4} max={6} unit="파울" />
          </div>

          <SectionHead num="04" label="3점 라인" sub="3-POINT LINE · 코트 측정 기준" mt={20} />
          <div style={{ display: "grid", gridTemplateColumns: "auto 1fr", gap: 18, alignItems: "center" }}>
            {/* Court mini-diagram */}
            <CourtDiagram threshold={rules.threshold} />
            <div>
              <div style={{ display: "flex", gap: 6, marginBottom: 10 }}>
                {[
                  { v: 6.75, label: "FIBA · 6.75m" },
                  { v: 6.60, label: "WNBA · 6.60m" },
                  { v: 7.24, label: "NBA · 7.24m" },
                  { v: 6.25, label: "학원 · 6.25m" },
                ].map((opt, i) => (
                  <button key={i} onClick={() => setRule("threshold", opt.v)}
                    style={{
                      padding: "6px 10px", fontFamily: "var(--f-mono)", fontSize: 10, fontWeight: 700,
                      letterSpacing: 0.5, cursor: "pointer",
                      background: rules.threshold === opt.v ? "var(--hot)" : "var(--bg-2)",
                      color: rules.threshold === opt.v ? "#0A0B0D" : "var(--fg-2)",
                      border: "1px solid var(--line-3)",
                    }}>{opt.label}</button>
                ))}
              </div>
              <p style={{ margin: 0, fontFamily: "var(--f-display)", fontSize: 13, color: "var(--fg-2)", lineHeight: 1.5, maxWidth: 460 }}>
                3점 라인 거리는 카메라 트래킹 시스템이 슛 거리를 환산할 때 사용합니다.
                대회 표준에 맞게 설정해 주세요.
              </p>
            </div>
          </div>
        </main>

        {/* === RIGHT — Local / custom rules === */}
        <aside style={{ background: "var(--bg-1)", padding: "18px 16px", overflow: "auto", minHeight: 0 }}>
          <SectionHead num="05" label="로컬 룰" sub="Local rules · 대회만의 추가 규정" />

          <div style={{ marginBottom: 10 }}>
            {localRules.map((r) => (
              <div key={r.id}
                style={{
                  display: "grid", gridTemplateColumns: "26px 1fr auto",
                  alignItems: "center", padding: "10px 8px",
                  borderBottom: "1px solid var(--line-1)",
                  background: r.on ? "var(--bg-2)" : "transparent",
                  cursor: "pointer",
                }}
                onClick={() => toggleLocal(r.id)}>
                <span style={{
                  width: 18, height: 18, border: `1.5px solid ${r.on ? "var(--hot)" : "var(--line-3)"}`,
                  background: r.on ? "var(--hot)" : "transparent",
                  display: "inline-flex", alignItems: "center", justifyContent: "center",
                  fontFamily: "var(--f-mono)", fontSize: 10, fontWeight: 800,
                  color: r.on ? "#0A0B0D" : "transparent",
                }}>{r.on ? "✓" : ""}</span>
                <span style={{ fontFamily: "var(--f-display)", fontSize: 12, fontWeight: 500,
                              color: r.on ? "var(--fg-0)" : "var(--fg-2)", lineHeight: 1.3 }}>
                  {r.label}
                </span>
                <span style={{
                  fontFamily: "var(--f-mono)", fontSize: 10, fontWeight: 700,
                  color: r.on ? "var(--hot)" : "var(--fg-3)", letterSpacing: 0.5,
                  minWidth: 36, textAlign: "right",
                }}>{r.value}</span>
              </div>
            ))}
          </div>

          <button className="cv-btn ghost" style={{ width: "100%", height: 36, fontSize: 11 }}>
            + 로컬 룰 추가
          </button>

          <SectionHead num="06" label="페널티 매트릭스" sub="Penalty matrix" mt={22} />
          <div style={{ background: "var(--bg-2)", border: "1px solid var(--line-2)" }}>
            {[
              ["P · 일반파울", "1FT × 2 / 점유 X", "var(--fg-2)"],
              ["U · 비신사적", "2FT + 점유", "var(--warn)"],
              ["T · 기술파울", "1FT + 점유", "var(--warn)"],
              ["D · 실격", "2FT + 점유 + 퇴장", "var(--bad)"],
            ].map(([k, v, c], i) => (
              <div key={i} style={{
                display: "grid", gridTemplateColumns: "1fr auto",
                padding: "9px 10px", borderBottom: i < 3 ? "1px solid var(--line-1)" : "none",
                fontFamily: "var(--f-mono)", fontSize: 10,
              }}>
                <span style={{ color: c, fontWeight: 700, letterSpacing: 0.5 }}>{k}</span>
                <span style={{ color: "var(--fg-1)" }}>{v}</span>
              </div>
            ))}
          </div>
        </aside>
      </div>

      {/* Footer — apply */}
      <div style={{ borderTop: "1px solid var(--line-2)", background: "var(--bg-0)", padding: "12px 24px",
                    display: "grid", gridTemplateColumns: "auto 1fr auto auto", gap: 18, alignItems: "center" }}>
        <span className="cv-tag" style={{ background: "var(--hot)", color: "#0A0B0D", border: "none" }}>
          {presets.find(p => p.id === activePreset)?.name} BASE
        </span>
        <span style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", letterSpacing: 1 }}>
          {rules.periods}Q × {rules.length} · 슛클락 {rules.shotClock}s · 보너스 {rules.bonus}파울 · TO {rules.totalTO}회 · 3PT {rules.threshold}m
          <span style={{ marginLeft: 12, color: "var(--good)" }}>+ 로컬 {localRules.filter(r => r.on).length}개</span>
        </span>
        <button className="cv-btn">미리보기</button>
        <button className="cv-btn primary" style={{ height: 38, padding: "0 20px" }}>
          전체 시스템에 적용 →
        </button>
      </div>
    </div>
  );
}

// -----------------------------------------------------------------------------
// Helpers
// -----------------------------------------------------------------------------
function SectionHead({ num, label, sub, mt = 0 }) {
  return (
    <div style={{ marginTop: mt, marginBottom: 12, display: "flex", alignItems: "baseline", gap: 8 }}>
      <span style={{ fontFamily: "var(--f-mono)", fontSize: 9, color: "var(--fg-3)", letterSpacing: 1.5 }}>{num}</span>
      <span style={{ fontFamily: "var(--f-display)", fontSize: 13, fontWeight: 700, letterSpacing: -0.2 }}>{label}</span>
      {sub && <span style={{ fontFamily: "var(--f-mono)", fontSize: 9, color: "var(--fg-3)", letterSpacing: 1 }}>· {sub}</span>}
      <span style={{ flex: 1, height: 1, background: "var(--line-2)" }}></span>
    </div>
  );
}

function RuleCard({ label, sub, value, onChange, type = "num", min, max, unit }) {
  return (
    <div style={{ background: "var(--bg-2)", border: "1px solid var(--line-2)", padding: "12px 14px" }}>
      <div style={{ fontFamily: "var(--f-display)", fontSize: 12, fontWeight: 600, color: "var(--fg-0)", marginBottom: 1 }}>{label}</div>
      <div style={{ fontFamily: "var(--f-mono)", fontSize: 8, color: "var(--fg-3)", letterSpacing: 1.2, marginBottom: 8 }}>{sub}</div>
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        {type === "num" ? (
          <>
            <button className="cv-btn" style={{ width: 26, height: 30, padding: 0, fontSize: 14 }}
              onClick={() => onChange(Math.max(min ?? 0, value - 1))}>−</button>
            <input value={value} onChange={(e) => onChange(e.target.value)}
              style={{
                flex: 1, background: "var(--bg-1)", border: "1px solid var(--line-3)", height: 30,
                color: "var(--fg-0)", fontFamily: "var(--f-mono)", fontSize: 16, fontWeight: 700,
                textAlign: "center", outline: "none", padding: 0,
              }} />
            <button className="cv-btn" style={{ width: 26, height: 30, padding: 0, fontSize: 14 }}
              onClick={() => onChange(Math.min(max ?? 99, value + 1))}>+</button>
            {unit && <span style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-3)", marginLeft: 2, minWidth: 24 }}>{unit}</span>}
          </>
        ) : (
          <input value={value} onChange={(e) => onChange(e.target.value)}
            style={{
              flex: 1, background: "var(--bg-1)", border: "1px solid var(--line-3)", height: 30,
              color: "var(--fg-0)", fontFamily: "var(--f-mono)", fontSize: 14, fontWeight: 700,
              textAlign: "center", outline: "none", padding: 0,
            }} />
        )}
      </div>
    </div>
  );
}

function CourtDiagram({ threshold = 6.75 }) {
  const w = 200, h = 130;
  // arc "depth" tied loosely to threshold for visual feedback
  const arcR = 30 + (threshold - 6.0) * 22;
  return (
    <svg width={w} height={h} style={{ background: "var(--bg-2)", border: "1px solid var(--line-2)", display: "block" }}>
      {/* court bounds */}
      <rect x={6} y={6} width={w - 12} height={h - 12} fill="none" stroke="var(--line-3)" strokeWidth={1} />
      {/* halfcourt line */}
      <line x1={w / 2} y1={6} x2={w / 2} y2={h - 6} stroke="var(--line-3)" strokeWidth={1} />
      {/* center circle */}
      <circle cx={w / 2} cy={h / 2} r={14} fill="none" stroke="var(--line-3)" strokeWidth={1} />
      {/* hoops + 3pt */}
      <circle cx={20} cy={h / 2} r={3} fill="var(--hot)" />
      <path d={`M 20 ${h / 2 - arcR} A ${arcR} ${arcR} 0 0 1 20 ${h / 2 + arcR}`}
        fill="none" stroke="var(--hot)" strokeWidth={1.5} />
      <circle cx={w - 20} cy={h / 2} r={3} fill="var(--cool)" />
      <path d={`M ${w - 20} ${h / 2 - arcR} A ${arcR} ${arcR} 0 0 0 ${w - 20} ${h / 2 + arcR}`}
        fill="none" stroke="var(--cool)" strokeWidth={1.5} />
      {/* threshold label */}
      <text x={w / 2} y={h - 12} textAnchor="middle"
        fontFamily="var(--f-mono)" fontSize={10} fill="var(--fg-2)" letterSpacing={1}>
        {threshold.toFixed(2)} m
      </text>
    </svg>
  );
}

window.CvRulesScreen = CvRulesScreen;
