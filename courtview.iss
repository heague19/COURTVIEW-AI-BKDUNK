; COURTVIEW Desktop — Inno Setup Installer Script
;
; 사전 요구: Inno Setup 6 설치 (https://jrsoftware.org/isdl.php)
; 번들 준비: python build.py X.Y.Z --clean  (dist\courtview\ 필요)
; 컴파일:    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" courtview.iss
; 산출물:    dist\COURTVIEW-Setup-X.Y.Z.exe
;
; 설계 포인트:
;  1. shortcut WorkingDir={userappdata} — Start-in 을 설치 폴더 밖으로 두어
;     auto-update 시 install 디렉토리 잠김 이슈 근본 회피.
;  2. AppId GUID 고정 — 동일 GUID 유지해야 업그레이드 설치가 제대로 인식됨.
;  3. v0.1.2 이후 per-user 설치 (%LOCALAPPDATA%\Programs\COURTVIEW) —
;     auto-update 가 일반 사용자 권한으로 staging/move 가능해 UAC 재요청 없음.
;     이전 Program Files 설치본은 [Code] InitializeSetup 에서 감지·안내.
;  4. MyAppVersion 은 ISCC 호출 시 /DMyAppVersion=0.1.2 으로 외부에서 주입 권장
;     (build.py 결과와 동기화). 기본값 은 fallback.

#ifndef MyAppVersion
  #define MyAppVersion "0.1.0"
#endif

#define MyAppName      "COURTVIEW"
#define MyAppPublisher "SPOIN-Inc"
#define MyAppURL       "https://github.com/SPOIN-Inc/COURTVIEW_DESK"
#define MyAppExeName   "courtview.exe"
#define SourceDir      "dist\courtview"

[Setup]
; --- 식별자 (GUID 고정, 업그레이드 연속성) ---
AppId={{B2A3D4E5-F6A7-4B8C-9D0E-1F2A3B4C5D6E}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; --- 설치 경로 (per-user, 사용자 권한만으로 auto-update 가능) ---
DefaultDirName={localappdata}\Programs\{#MyAppName}
DisableProgramGroupPage=yes
DefaultGroupName={#MyAppName}

; --- 산출물 ---
OutputDir=dist
OutputBaseFilename=COURTVIEW-Setup-{#MyAppVersion}
SetupIconFile=
WizardStyle=modern

; --- 압축 ---
; v0.5.7.6: SolidCompression=yes + lzma2/max 가 262MB+ dll (TensorRT, torch) 일부에서
; 결정론적으로 압축 해제 손상 유발 (사용자 0.5.7.5 install 2회 연속 같은 .dll CRC 실패).
; solid 블록 안에서 한 dll 글리치가 chain corruption → 다른 파일까지 깨뜨림.
; 해결: solid 끄고 per-file lzma2/normal — 파일별 독립 압축으로 격리.
; 트레이드: zip 사이즈 ~5.86 GB → ~6.2 GB (4-6%↑) 받지만 무결성 보장.
Compression=lzma2/normal
SolidCompression=no
LZMANumBlockThreads=4

; --- 디스크 분할 (번들 9.43 GB > Inno 단일 .exe 4.2 GB 한계) ---
; Setup.exe + COURTVIEW-Setup-0.1.0-2.bin, -3.bin ... 로 분할 생성.
; 사용자는 Setup.exe 클릭만 하면 같은 폴더의 .bin 들을 자동 인식.
; USB 복사 시 Setup.exe + 모든 .bin 을 같이 옮기면 됨.
DiskSpanning=yes
DiskSliceSize=2100000000

; --- 권한/아키텍처 ---
; per-user 설치 — 관리자 승격 불필요, auto-update 도 UAC 없이 작동
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763

; --- UI ---
ShowLanguageDialog=no
DisableWelcomePage=no
DisableReadyPage=no
UninstallDisplayName={#MyAppName} {#MyAppVersion}
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "korean";  MessagesFile: "compiler:Languages\Korean.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "바탕화면에 아이콘 생성"; GroupDescription: "추가 아이콘:"; Flags: unchecked

[Files]
; dist\courtview\ 전체를 {app} 에 복사
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; --- 핵심 ---
; WorkingDir={userappdata} 로 shortcut 의 Start-in 을 %APPDATA% 로 지정.
; 이게 없으면 shortcut 실행 시 cwd=install 이 되어 auto-update 의 rename
; (ERROR_SHARING_VIOLATION) 실패. 실측으로 재현된 이슈.
Name: "{group}\{#MyAppName}"; \
      Filename: "{app}\{#MyAppExeName}"; \
      WorkingDir: "{userappdata}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; \
      Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; \
      Filename: "{app}\{#MyAppExeName}"; \
      WorkingDir: "{userappdata}"; \
      Tasks: desktopicon

[Run]
; 설치 직후 "지금 실행" 옵션 (기본 체크). WorkingDir 동일하게 %APPDATA%.
Filename: "{app}\{#MyAppExeName}"; \
  Description: "{cm:LaunchProgram,{#MyAppName}}"; \
  WorkingDir: "{userappdata}"; \
  Flags: postinstall nowait skipifsilent

[UninstallDelete]
; 설치 디렉토리 내에 런타임 생성될 수 있는 잔해 (auto-update 중단 시)
Type: filesandordirs; Name: "{app}\.courtview_new_*"
Type: filesandordirs; Name: "{app}\..\.courtview_new_*"
Type: files;          Name: "{app}\..\_courtview_swap.bat"
Type: files;          Name: "{app}\..\_courtview_swap.log"

[Code]
// v0.1.0 / v0.1.1 은 Program Files 에 per-machine(admin) 설치됐음.
// v0.1.2 부터 %LOCALAPPDATA%\Programs 로 per-user 이관.
// 설치 시작 시 기존 Program Files 설치를 감지해 사용자에게 제거 안내.
function InitializeSetup(): Boolean;
var
  OldPath:       string;
  OldExePath:    string;
  UninstKey:     string;
  Uninstaller:   string;
  ResultCode:    Integer;
  MsgResult:     Integer;
begin
  Result := True;

  OldPath    := ExpandConstant('{pf}\COURTVIEW');
  OldExePath := OldPath + '\courtview.exe';
  UninstKey  := 'Software\Microsoft\Windows\CurrentVersion\Uninstall\' +
                '{B2A3D4E5-F6A7-4B8C-9D0E-1F2A3B4C5D6E}_is1';

  if not FileExists(OldExePath) then
    Exit;

  // 기존 Program Files 설치 감지됨
  MsgResult := MsgBox(
    '이전 버전 COURTVIEW 가 관리자 권한으로 설치돼있습니다.' + #13#10 +
    '경로: ' + OldPath + #13#10 + #13#10 +
    'v0.1.2 부터는 일반 사용자 권한 경로(%LOCALAPPDATA%) 에 설치됩니다.' + #13#10 +
    'auto-update 가 UAC 없이 작동하도록 하기 위한 구조 변경입니다.' + #13#10 + #13#10 +
    '기존 설치를 지금 제거할까요? (강력 권장)',
    mbConfirmation, MB_YESNO);

  if MsgResult <> IDYES then begin
    MsgBox('기존 설치를 수동으로 제거한 뒤 본 설치를 다시 실행해주세요.' + #13#10 +
           '(설정 > 앱 > COURTVIEW > 제거)',
           mbInformation, MB_OK);
    Result := False;
    Exit;
  end;

  // 레지스트리에서 uninstaller 경로 조회 + 실행
  if RegQueryStringValue(HKLM, UninstKey, 'UninstallString', Uninstaller) then begin
    // UninstallString 는 보통 따옴표 포함 — RemoveQuotes
    Uninstaller := RemoveQuotes(Uninstaller);
    if not Exec(Uninstaller, '/SILENT /NORESTART', '', SW_HIDE,
                ewWaitUntilTerminated, ResultCode) then begin
      MsgBox('이전 설치 제거 실행 실패. 수동으로 제거 후 다시 시도해주세요.',
             mbError, MB_OK);
      Result := False;
    end;
  end else begin
    MsgBox('기존 uninstaller 를 찾을 수 없습니다.' + #13#10 +
           '설정 > 앱 > COURTVIEW > 제거 후 다시 실행해주세요.',
           mbError, MB_OK);
    Result := False;
  end;
end;
