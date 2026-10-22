; One installer for Qirtas (TASKS item 2). Built by installer\build.ps1 from
; the PyInstaller folder installer\dist\Qirtas.

[Setup]
AppName=Qirtas
AppVerName=Qirtas 0.1
AppPublisher=Moaz Alchayah
DefaultDirName={autopf}\Qirtas
DefaultGroupName=Qirtas
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=Output
OutputBaseFilename=Qirtas-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\Qirtas.exe

[Languages]
Name: "arabic"; MessagesFile: "compiler:Languages\Arabic.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "dist\Qirtas\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Qirtas"; Filename: "{app}\Qirtas.exe"
Name: "{autodesktop}\Qirtas"; Filename: "{app}\Qirtas.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Qirtas.exe"; Description: "{cm:LaunchProgram,Qirtas}"; Flags: nowait postinstall skipifsilent

[Code]
// Every conversion renders through Microsoft Word (FLAGS 26): say so before
// installing, rather than failing on the first file.
function InitializeSetup(): Boolean;
begin
  Result := True;
  if not RegKeyExists(HKEY_CLASSES_ROOT, 'Word.Application') then
    Result := MsgBox('Qirtas needs Microsoft Word, and Word was not found on this computer.' + #13#10 +
                     'يحتاج قرطاس إلى برنامج مايكروسوفت وورد، ولم يُعثر عليه في هذا الحاسوب.' + #13#10#13#10 +
                     'Install anyway?', mbConfirmation, MB_YESNO) = IDYES;
end;
