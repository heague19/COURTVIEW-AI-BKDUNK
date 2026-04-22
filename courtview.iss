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
;  3. Program Files 에 설치 → PrivilegesRequired=admin, 64-bit 모드.
;  4. MyAppVersion 은 ISCC 호출 시 /DMyAppVersion=0.1.0 으로 외부에서 주입 권장
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

; --- 설치 경로 ---
DefaultDirName={autopf}\{#MyAppName}
DisableProgramGroupPage=yes
DefaultGroupName={#MyAppName}

; --- 산출물 ---
OutputDir=dist
OutputBaseFilename=COURTVIEW-Setup-{#MyAppVersion}
SetupIconFile=
WizardStyle=modern

; --- 압축 ---
Compression=lzma2/max
SolidCompression=yes
LZMANumBlockThreads=4

; --- 디스크 분할 (번들 9.43 GB > Inno 단일 .exe 4.2 GB 한계) ---
; Setup.exe + COURTVIEW-Setup-0.1.0-2.bin, -3.bin ... 로 분할 생성.
; 사용자는 Setup.exe 클릭만 하면 같은 폴더의 .bin 들을 자동 인식.
; USB 복사 시 Setup.exe + 모든 .bin 을 같이 옮기면 됨.
DiskSpanning=yes
DiskSliceSize=2100000000

; --- 권한/아키텍처 ---
PrivilegesRequired=admin
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
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
