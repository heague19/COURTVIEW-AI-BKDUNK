// =============================================================================
// COURTVIEW — System UI demo screen (showcases EmptyState, Skeleton, Toast, Confirm, ON AIR)
// =============================================================================

function CvSystemUIDemo() {
  const toast = window.useToast();
  const confirm = window.useConfirm();
  const [loading, setLoading] = React.useState(false);

  const handleFinalize = async () => {
    const ok = await confirm({
      title: "이 경기를 종료하고 finalize 하시겠어요?",
      body: "종료하면 더 이상 기록을 추가/수정할 수 없습니다. 박스스코어는 즉시 클라우드로 업로드됩니다.",
      detail: "MATCH-ID · 2026-05-07-FAL-TIT-S1\nDURATION · 38m 12s · 4 quarters · 142 events",
      confirmText: "FINALIZE",
      destructive: false,
    });
    if (ok) toast.success("FINALIZED", "박스스코어가 BKDUNK 클라우드로 업로드되었습니다.");
  };
  const handleDelete = async () => {
    const ok = await confirm({
      title: "정말 이 경기를 삭제하시겠어요?",
      body: "삭제된 데이터는 복구할 수 없습니다. 영상 클립과 박스스코어 모두 함께 제거됩니다.",
      detail: "MATCH-ID · 2026-05-06-VOL-TIT-S2\n12 highlights · 84 stats events",
      confirmText: "DELETE PERMANENTLY",
      destructive: true,
    });
    if (ok) toast.error("DELETED", "경기 데이터가 영구 삭제되었습니다.");
  };

  return (
    <div style={{ background: "var(--bg-1)", color: "var(--fg-0)", height: "100%", display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <window.TopNav active="settings" />
      <div style={{ flex: 1, overflow: "auto" }}>
        <window.EdHero
          issue="SYS · 001"
          tag="cool" tagText="SYSTEM"
          kicker="BUILDING BLOCKS · TONE & FEEDBACK PATTERNS"
          title={{ primary: "THE QUIET", accent: "VOICE." }}
          subline={[
            { k: "TOAST", v: "4 KINDS" },
            { k: "DIALOG", v: "DESTRUCTIVE / CONFIRM" },
            { k: "EMPTY", v: "RULE-LINED" },
            { k: "LOADING", v: "PULSING SKELETON" },
          ]}
        />

        {/* Toasts */}
        <window.EdPanel kicker="01 · TOASTS" title="알림 · 자기-소거되는 시스템 메시지" padding="28px 48px">
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button className="cv-btn" onClick={() => toast.info("CAMERA RECONNECTED", "CAM 03 · 4K · 60fps · stream live")}>● INFO</button>
            <button className="cv-btn" onClick={() => toast.success("UPLOAD COMPLETE", "박스스코어가 클라우드로 업로드되었습니다.")}>● SUCCESS</button>
            <button className="cv-btn" onClick={() => toast.warn("LOW DISK", "녹화 가능 시간 12분 · 외장 SSD 연결 권장")}>● WARN</button>
            <button className="cv-btn" onClick={() => toast.error("STREAM LOST", "RTMP 연결 끊김 · 재시도 중 (3/5)")}>● ERROR</button>
            <button className="cv-btn ghost" onClick={() => {
              toast.info("Q3 START", "3쿼터 시작 · 12:00");
              setTimeout(() => toast.success("CLIP SAVED", "K. PARK · step-back 3"), 600);
              setTimeout(() => toast.warn("FOUL LIMIT", "M. HAN · PF 4/5 · approaching limit"), 1200);
            }}>▶ DEMO SEQUENCE</button>
          </div>
        </window.EdPanel>

        {/* Confirm */}
        <window.EdPanel kicker="02 · CONFIRM DIALOG" title="결정적 액션 — 두 단계 확인" padding="28px 48px">
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button className="cv-btn primary" onClick={handleFinalize} style={{ height: 36 }}>✓ FINALIZE GAME</button>
            <button className="cv-btn" onClick={handleDelete} style={{ height: 36, borderColor: "var(--bad)", color: "var(--bad)" }}>✕ DELETE GAME</button>
          </div>
          <div style={{ marginTop: 14, fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-3)", letterSpacing: 0.5, lineHeight: 1.7 }}>
            destructive=true → 빨간 강조 / DELETE 라벨 / WARN 키커.<br/>
            destructive=false → 오렌지 강조 / CONFIRM 라벨. 둘 다 backdrop 클릭 / ESC / ✕로 취소 가능.
          </div>
        </window.EdPanel>

        {/* EmptyState */}
        <window.EdPanel kicker="03 · EMPTY STATES" title="데이터 없음 — 무엇을 할 수 있는지 알려준다" padding="28px 48px">
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
            <window.EdEmptyState
              kicker="NO GAMES YET"
              title="첫 경기를 시작하세요"
              body="DESK는 아직 어떤 경기도 기록하지 않았습니다. 카메라가 연결되어 있다면 OPERATOR로 이동해 라이브 기록을 시작할 수 있습니다."
              action={<button className="cv-btn primary" style={{ height: 32 }}>▶ START LIVE GAME</button>}
            />
            <window.EdEmptyState
              kicker="NO RESULTS MATCH"
              title="필터에 맞는 경기가 없어요"
              body="다른 날짜나 팀 조합을 시도해 보세요."
              action={<button className="cv-btn ghost" style={{ height: 32 }}>↺ RESET FILTERS</button>}
            />
          </div>
        </window.EdPanel>

        {/* Skeleton */}
        <window.EdPanel kicker="04 · LOADING SKELETON" title="로딩 — 실제 행 모양 그대로" padding="28px 48px"
          right={
            <button className="cv-btn ghost" onClick={() => { setLoading(true); setTimeout(() => setLoading(false), 2200); }} style={{ height: 28 }}>
              {loading ? "● LOADING…" : "▶ TOGGLE LOADING (2.2s)"}
            </button>
          }>
          {loading ? (
            <window.EdSkeleton rows={6} height={42} />
          ) : (
            <div style={{ display: "grid", gap: 10 }}>
              {[
                { d: "2026-05-07", h: "FALCONS", a: "TITANS", s: "78–64" },
                { d: "2026-05-07", h: "VOLTS",   a: "BLAZERS", s: "41–38 · LIVE" },
                { d: "2026-05-06", h: "STORM",   a: "RIDERS", s: "82–79" },
                { d: "2026-05-06", h: "FALCONS", a: "PHANTOMS", s: "91–70" },
                { d: "2026-05-05", h: "BLAZERS", a: "CRUSADERS", s: "88–85" },
                { d: "2026-05-05", h: "VOLTS",   a: "TITANS", s: "95–67" },
              ].map((g, i) => (
                <div key={i} style={{ height: 42, padding: "0 14px", display: "grid", gridTemplateColumns: "100px 1fr 140px", alignItems: "center", borderLeft: "2px solid var(--line-3)", background: "var(--bg-2)" }}>
                  <span style={{ fontFamily: "var(--f-mono)", fontSize: 11, color: "var(--fg-3)" }}>{g.d}</span>
                  <span style={{ fontFamily: "var(--f-display)", fontSize: 14, fontWeight: 700 }}>{g.h} <span style={{ color: "var(--fg-3)" }}>vs</span> {g.a}</span>
                  <span style={{ fontFamily: "var(--f-mono)", fontSize: 11, color: "var(--hot)", textAlign: "right" }}>{g.s}</span>
                </div>
              ))}
            </div>
          )}
        </window.EdPanel>

        {/* ON AIR */}
        <window.EdPanel kicker="05 · ON-AIR BADGE" title="라이브 상태 — 한 눈에 보이는" padding="28px 48px">
          <div style={{ display: "flex", gap: 24, alignItems: "center", flexWrap: "wrap" }}>
            <window.EdOnAir size="sm" />
            <window.EdOnAir size="md" />
            <window.EdOnAir size="lg" />
            <span style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-3)", letterSpacing: 1 }}>
              S · M · L — Operator 좌상단(L) · Scoreboard 코너(M) · 헤더 인라인(S)
            </span>
          </div>
        </window.EdPanel>
      </div>
    </div>
  );
}

window.CvSystemUIDemo = CvSystemUIDemo;
