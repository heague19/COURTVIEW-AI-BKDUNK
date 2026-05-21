# 24.13 카메라 복구 체크 — cold boot 15분 후 실행
# Usage: powershell -ExecutionPolicy Bypass -File _camera_check_24_13.ps1

$ErrorActionPreference = 'Continue'
$target = '169.254.24.13'

Write-Host "=== 24.13 cold-boot 복구 체크 ===" -ForegroundColor Cyan
Write-Host ""

# 1) Ping — ARP 진입 유도
Write-Host "[1/4] ping (ARP prewarm, 4 packets)..." -ForegroundColor Yellow
$ping = Test-Connection -ComputerName $target -Count 4 -Quiet
Write-Host "     결과: $ping"
Write-Host ""

# 2) ARP — MAC 확인
Write-Host "[2/4] ARP 테이블 (24.13 MAC 존재 여부)..." -ForegroundColor Yellow
$arp = arp -a | Select-String "169\.254\.24\.13"
if ($arp) {
    Write-Host "     $arp" -ForegroundColor Green
} else {
    Write-Host "     MAC 없음 — 카메라 네트워크 스택 미기동" -ForegroundColor Red
}
Write-Host ""

# 3) TCP 554 — RTSP 포트 열림 확인
Write-Host "[3/4] TCP 554 reachability..." -ForegroundColor Yellow
$tcp = Test-NetConnection -ComputerName $target -Port 554 -InformationLevel Quiet -WarningAction SilentlyContinue
if ($tcp) {
    Write-Host "     OPEN (554 reachable)" -ForegroundColor Green
} else {
    Write-Host "     CLOSED (554 unreachable)" -ForegroundColor Red
}
Write-Host ""

# 4) RTSP DESCRIBE — 실제 RTSP 서비스 응답 확인
Write-Host "[4/4] RTSP DESCRIBE /11 응답..." -ForegroundColor Yellow
try {
    $client = New-Object System.Net.Sockets.TcpClient
    $task = $client.ConnectAsync($target, 554)
    if ($task.Wait(2000)) {
        $stream = $client.GetStream()
        $req = "DESCRIBE rtsp://$($target):554/11 RTSP/1.0`r`nCSeq: 1`r`nAccept: application/sdp`r`nUser-Agent: CourtView/CoolCheck`r`n`r`n"
        $bytes = [Text.Encoding]::ASCII.GetBytes($req)
        $stream.Write($bytes, 0, $bytes.Length)
        $stream.ReadTimeout = 2000
        $buf = New-Object byte[] 1024
        $n = $stream.Read($buf, 0, 1024)
        $resp = [Text.Encoding]::ASCII.GetString($buf, 0, $n)
        $firstLine = $resp.Split("`r`n")[0]
        Write-Host "     $firstLine" -ForegroundColor Green
    } else {
        Write-Host "     2초 내 연결 실패" -ForegroundColor Red
    }
    $client.Close()
} catch {
    Write-Host "     예외: $_" -ForegroundColor Red
}
Write-Host ""
Write-Host "=== 완료 ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "판정 기준:"
Write-Host "  [O] 모두 통과  -> 카메라 복구됨. v0.2.2 빌드 결과 테스트 진행."
Write-Host "  [X] ARP 없음   -> 케이블/PoE 확인. 다른 포트에 꽂기."
Write-Host "  [X] 554 CLOSED -> 펌웨어 완전 잠금. 리셋 핀 10초(공장 초기화) 필요."
