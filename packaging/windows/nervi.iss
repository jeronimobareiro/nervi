; SPDX-License-Identifier: GPL-3.0-or-later
; Instalador de Windows (Inno Setup 6). Se compila desde el CI de publicación:
;   iscc /DVersion=0.1.0 /DOrigen=dist\Nervi /DIconos=build\iconos packaging\windows\nervi.iss
; Asociación de .nrv según docs/formato-nrv.md §7.1: no pisa una asociación existente
; (por ejemplo la de Nero); agrega Nervi a "Abrir con" y ofrece hacerlo predeterminado.

#ifndef Version
  #define Version "0.0.0"
#endif
#ifndef Origen
  #define Origen "..\..\dist\Nervi"
#endif
#ifndef Iconos
  #define Iconos "..\..\build\iconos"
#endif

[Setup]
AppId={{5B0F6C64-6E2D-4C0B-9A57-4E8E2B3A9F11}
AppName=Nervi
AppVersion={#Version}
AppVerName=Nervi {#Version} (versión preliminar)
AppPublisher=Proyecto Nervi
AppPublisherURL=https://github.com/jeronimobareiro/nervi
AppSupportURL=https://github.com/jeronimobareiro/nervi/issues
DefaultDirName={autopf}\Nervi
DefaultGroupName=Nervi
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ChangesAssociations=yes
LicenseFile=..\..\LICENSE
OutputDir=..\..\dist
OutputBaseFilename=Nervi-{#Version}-windows-x64
SetupIconFile={#Iconos}\nervi.ico
UninstallDisplayIcon={app}\Nervi.exe
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "escritorio"; Description: "Crear un acceso directo en el escritorio"; Flags: unchecked
Name: "asociar"; Description: "Abrir los archivos .nrv con Nervi"; Check: not NrvAsociadoAOtro
Name: "asociar"; Description: "Abrir los archivos .nrv con Nervi (hoy los abre otro programa)"; Flags: unchecked; Check: NrvAsociadoAOtro

[Files]
Source: "{#Origen}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#Iconos}\nervi.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Nervi"; Filename: "{app}\Nervi.exe"
Name: "{autodesktop}\Nervi"; Filename: "{app}\Nervi.exe"; Tasks: escritorio

[Registry]
; Siempre: Nervi aparece en "Abrir con" para .nrv
Root: HKA; Subkey: "Software\Classes\.nrv\OpenWithProgids"; ValueType: string; ValueName: "Nervi.Proyecto.1"; ValueData: ""; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\Nervi.Proyecto.1"; ValueType: string; ValueName: ""; ValueData: "Proyecto de Nervi"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\Nervi.Proyecto.1\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: """{app}\nervi.ico"",0"
Root: HKA; Subkey: "Software\Classes\Nervi.Proyecto.1\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\Nervi.exe"" ""%1"""
; Solo si el usuario lo elige: Nervi como programa predeterminado de .nrv
Root: HKA; Subkey: "Software\Classes\.nrv"; ValueType: string; ValueName: ""; ValueData: "Nervi.Proyecto.1"; Flags: uninsdeletevalue; Tasks: asociar
Root: HKA; Subkey: "Software\Classes\.nrv"; ValueType: string; ValueName: "Content Type"; ValueData: "application/vnd.nervi.proyecto+zip"; Flags: uninsdeletevalue; Tasks: asociar

[Run]
Filename: "{app}\Nervi.exe"; Description: "Abrir Nervi"; Flags: nowait postinstall skipifsilent

[Code]
function NrvAsociadoAOtro: Boolean;
var
  Actual: String;
begin
  Result := RegQueryStringValue(HKCR, '.nrv', '', Actual) and (Actual <> '') and (Actual <> 'Nervi.Proyecto.1');
end;
