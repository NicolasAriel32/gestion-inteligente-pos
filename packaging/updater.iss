; Actualizador separado: se instala FUERA de la carpeta del POS para poder reemplazarla.
#ifndef UpdaterVersion
  #define UpdaterVersion "1.0.0"
#endif
[Setup]
AppId={{6C2B1E0A-5D7F-4C3B-9A61-2F0E8D4B7A13}
AppName=Actualizador de Gestión Inteligente POS
AppVersion={#UpdaterVersion}
DefaultDirName={localappdata}\Programs\GestionInteligentePOS-Actualizador
DefaultGroupName=Gestión Inteligente POS
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.22000
OutputDir=..\dist\installer
OutputBaseFilename=ActualizadorPOS-{#UpdaterVersion}-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\ActualizadorPOS.exe
[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
[Files]
Source: "..\dist\ActualizadorPOS.exe"; DestDir: "{app}"; Flags: ignoreversion
[Icons]
Name: "{group}\Actualizador del POS (técnico)"; Filename: "{app}\ActualizadorPOS.exe"
