#if Ver < EncodeVer(6, 3, 0)
  #error "This file is UTF-8 encoded without a BOM, which requires Inno Setup 6.3.0 or later."
#endif

#ifndef Version
  #error "Version not defined. Pass /DVersion=x.y.z to ISCC."
#endif

#ifndef BuildDir
  #error "BuildDir not defined. Pass /DBuildDir=<absolute path>."
#endif

#ifndef OutputDir
  #error "OutputDir not defined. Pass /DOutputDir=<absolute path>."
#endif

[Setup]
AppId={{8A2C6A14-3B3D-4E2C-8A0E-7C9D1A0B2E33}
AppName=Speech2Anywhere
AppVersion={#Version}
AppPublisher=Mike Pollow
AppPublisherURL=https://github.com/MikeGT4/speech2anywhere
DefaultDirName={localappdata}\Kira
DefaultGroupName=Speech2Anywhere
DisableProgramGroupPage=yes
LicenseFile={#BuildDir}\..\installer\license.de.txt
OutputDir={#OutputDir}
OutputBaseFilename=Kira-Setup-v{#Version}
Compression=lzma2/max
SolidCompression=yes
DiskSpanning=yes
DiskSliceSize=2147483647
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
WizardImageFile={#BuildDir}\..\assets\wizard-side.bmp
WizardSmallImageFile={#BuildDir}\..\assets\wizard-small.bmp
WizardImageStretch=no
WizardImageBackColor=$1c1c1c
SetupIconFile={#BuildDir}\..\assets\icon-branded.ico
UninstallDisplayIcon={app}\assets\icon-branded.ico
UninstallDisplayName=Speech2Anywhere {#Version}
Uninstallable=yes

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"

[Messages]
WelcomeLabel1=Willkommen bei Speech2Anywhere v{#Version}
WelcomeLabel2=Diese Anwendung installiert Speech2Anywhere auf deinem Computer.%n%nBeim ersten Start lädt Speech2Anywhere rund 10 GB Modelle (Whisper und Gemma), dafür braucht es einmal Internet.%n%nKlicke auf „Weiter“, um fortzufahren.

FinishedHeadingLabel=Speech2Anywhere wurde installiert.
FinishedLabel=Speech2Anywhere ist installiert.%n%nBeim ersten Start öffnet sich der Einrichtungsassistent für die Modelle.
ClickFinish=Klicke auf „Fertigstellen“, um Speech2Anywhere zu starten.

[Tasks]
Name: "autostart"; Description: "Mit Windows starten"; GroupDescription: "Zusätzliche Optionen:"
Name: "desktopicon"; Description: "Verknüpfung auf dem Desktop"; GroupDescription: "Zusätzliche Optionen:"
Name: "startmenuicon"; Description: "Im Startmenü ablegen"; GroupDescription: "Zusätzliche Optionen:"

[Files]
Source: "{#BuildDir}\python\*"; DestDir: "{app}\python"; Flags: recursesubdirs ignoreversion

Source: "{#BuildDir}\kira-source\*"; DestDir: "{app}\app"; Flags: recursesubdirs ignoreversion

Source: "{#BuildDir}\wheels\*.whl"; DestDir: "{tmp}\kira-wheels"; Flags: deleteafterinstall

Source: "{#BuildDir}\rcedit-x64.exe"; DestDir: "{app}\tools"; DestName: "rcedit-x64.exe"; Flags: ignoreversion

Source: "{#BuildDir}\..\installer\embedded\OllamaSetup.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall
Source: "{#BuildDir}\..\installer\embedded\OllamaSetup.exe"; DestDir: "{app}\installer\embedded"; Flags: ignoreversion

Source: "{#BuildDir}\..\assets\icon-branded.ico"; DestDir: "{app}\assets"; Flags: ignoreversion
Source: "{#BuildDir}\..\installer\config.yaml.template"; DestDir: "{tmp}"; Flags: deleteafterinstall

[Dirs]
Name: "{app}\tools"
Name: "{userappdata}\Kira"

[InstallDelete]
Type: filesandordirs; Name: "{app}\python\Lib\site-packages\kira"
Type: filesandordirs; Name: "{app}\python\Lib\site-packages\kira-*"
Type: filesandordirs; Name: "{app}\venv"
Type: filesandordirs; Name: "{app}\app\assets"
Type: filesandordirs; Name: "{app}\app\installer"
Type: files; Name: "{userstartup}\Kira.lnk"
Type: files; Name: "{userdesktop}\Kira.lnk"
Type: files; Name: "{userprograms}\Kira.lnk"

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Icons]
Name: "{userdesktop}\Speech2Anywhere"; Filename: "{app}\python\Scripts\kira.exe"; \
    WorkingDir: "{app}"; IconFilename: "{app}\assets\icon-branded.ico"; \
    Tasks: desktopicon

Name: "{userprograms}\Speech2Anywhere"; Filename: "{app}\python\Scripts\kira.exe"; \
    WorkingDir: "{app}"; IconFilename: "{app}\assets\icon-branded.ico"; \
    Tasks: startmenuicon

Name: "{userstartup}\Speech2Anywhere"; Filename: "{app}\python\Scripts\kira.exe"; \
    WorkingDir: "{app}"; IconFilename: "{app}\assets\icon-branded.ico"; \
    Tasks: autostart

[Run]
Filename: "{app}\python\python.exe"; \
    Parameters: "-m pip install --no-index --no-build-isolation --find-links ""{tmp}\kira-wheels"" --no-warn-script-location ""kira[windows]"""; \
    StatusMsg: "Installiere Speech2Anywhere-Python-Pakete..."; \
    Flags: waituntilterminated

Filename: "{tmp}\OllamaSetup.exe"; \
    Parameters: "/S /NORESTART"; \
    StatusMsg: "Installiere Ollama..."; \
    Flags: waituntilterminated; \
    Check: NeedsOllama

Filename: "{app}\python\Scripts\kira.exe"; \
    Description: "Speech2Anywhere jetzt starten"; \
    Flags: postinstall nowait skipifsilent

[Code]
function InitializeSetup: Boolean;
begin
  Result := True;
end;

function NeedsOllama: Boolean;
begin
  Result := not FileExists(ExpandConstant('{localappdata}\Programs\Ollama\ollama.exe'));
end;

procedure WriteConfigIfMissing();
var
  ConfigPath, TemplatePath: String;
  TemplateBytes: AnsiString;
  UnicodeText: String;
  Username: String;
begin
  ConfigPath := ExpandConstant('{userappdata}\Kira\config.yaml');
  if FileExists(ConfigPath) then
    Exit;

  TemplatePath := ExpandConstant('{tmp}\config.yaml.template');
  if not LoadStringFromFile(TemplatePath, TemplateBytes) then begin
    Log('config.yaml.template not found -- skipping config write');
    Exit;
  end;

  UnicodeText := UTF8Decode(TemplateBytes);

  Username := ExpandConstant('{username}');
  StringChangeEx(UnicodeText, '${USERNAME}', Username, True);

  ForceDirectories(ExpandConstant('{userappdata}\Kira'));
  if not SaveStringToFile(ConfigPath, Utf8Encode(UnicodeText), False) then
    Log('failed to write ' + ConfigPath);
end;

procedure VerifyKiraExeOrError();
var
  KiraExe: String;
begin
  KiraExe := ExpandConstant('{app}\python\Scripts\kira.exe');
  if not FileExists(KiraExe) then begin
    MsgBox(
      'Setup-Fehler: kira.exe wurde nicht erstellt unter' + #13#10 +
      KiraExe + '.' + #13#10#13#10 +
      'Pip-Install ist vermutlich silent fehlgeschlagen.' + #13#10 +
      'Bitte das Setup-Protokoll anhängen, wenn du den Fehler meldest:' + #13#10 +
      '  %TEMP%\Setup Log <DATUM>.txt' + #13#10#13#10 +
      'Issue-Tracker: https://github.com/MikeGT4/speech2anywhere/issues',
      mbCriticalError, MB_OK);
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then begin
    WriteConfigIfMissing();
    VerifyKiraExeOrError();
  end;
end;
