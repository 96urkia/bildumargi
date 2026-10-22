; Instalador de Bildumargi para Windows (Inno Setup 6).
;
; Instala la aplicación empaquetada con PyInstaller (build\windows\dist\
; Bildumargi) para el usuario, sin permisos de administrador, con accesos
; directos en el escritorio y en el menú Inicio. Pide, si se quiere, los
; datos de la biblioteca, la cuenta de DILVE y la ruta del catálogo MARC, y
; los deja en datos\instalacion.ini para que Bildumargi los aplique al
; arrancar (y lo borre: lleva la contraseña de DILVE).
;
; Los datos de uso viven en %LOCALAPPDATA%\Bildumargi\datos: actualizar a
; una versión nueva no los toca; al desinstalar se pregunta si se borran.
;
; Lo construye packaging\windows\construir.ps1.

#define Version "2.1"

[Setup]
AppId={{6E3B5E0A-6F4B-4C1B-9B1E-2B6A1C9D0F21}
AppName=Bildumargi
AppVersion={#Version}
AppVerName=Bildumargi {#Version}
AppPublisher=Asier Urkia
AppPublisherURL=https://github.com/96urkia/bildumargi
AppSupportURL=https://github.com/96urkia/bildumargi
DefaultDirName={autopf}\Bildumargi
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\..\build\windows
OutputBaseFilename=Bildumargi-{#Version}-instalador
SetupIconFile=bildumargi.ico
UninstallDisplayIcon={app}\Bildumargi.exe
UninstallDisplayName=Bildumargi {#Version}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "catalan"; MessagesFile: "compiler:Languages\Catalan.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
spanish.Abrir=Abrir Bildumargi
spanish.BibTitulo=Tu biblioteca
spanish.BibDesc=Datos para los indicadores (se pueden cambiar después en Configuración)
spanish.BibAyuda=Con la población se calculan los documentos por habitante; con la superficie, los documentos por m². Puedes dejarlo en blanco.
spanish.BibNombre=Nombre de la biblioteca:
spanish.BibRed=Red a la que pertenece (si es el caso):
spanish.BibPoblacion=Habitantes atendidos:
spanish.BibMetros=Superficie útil (m²):
spanish.DilveTitulo=Cuenta de DILVE (opcional)
spanish.DilveDesc=Para las sugerencias de compra y el idioma de los libros
spanish.DilveAyuda=DILVE es gratuito para bibliotecas: el usuario y la contraseña los da la FGEE. Si aún no los tienes, deja esto en blanco y escríbelos después en Configuración.
spanish.DilveUsuario=Usuario:
spanish.DilveClave=Contraseña:
spanish.MarcTitulo=Catálogo MARC (opcional)
spanish.MarcDesc=Para conocer el idioma de los libros antiguos
spanish.MarcAyuda=Si tienes el .db del catálogo (el de tu red o el que genera conversor.py), elige el fichero. Bildumargi tomará de él el idioma de tus ejemplares la primera vez que analices tus listados. Puedes dejarlo en blanco.
spanish.MarcFichero=Fichero .db del catálogo:
spanish.MarcFiltro=Bases de datos (*.db)|*.db|Todos los ficheros|*.*
spanish.NumeroMal=Escribe solo números en los habitantes y la superficie.
spanish.BorrarDatos=¿Borrar también los datos de Bildumargi (cargas guardadas, configuración y fichas de DILVE)?%n%nSi vas a reinstalarlo, elige «No» y los conservarás.
catalan.Abrir=Obre Bildumargi
catalan.BibTitulo=La teva biblioteca
catalan.BibDesc=Dades per als indicadors (es poden canviar després a Configuració)
catalan.BibAyuda=Amb la població es calculen els documents per habitant; amb la superfície, els documents per m². Ho pots deixar en blanc.
catalan.BibNombre=Nom de la biblioteca:
catalan.BibRed=Xarxa a la qual pertany (si escau):
catalan.BibPoblacion=Habitants atesos:
catalan.BibMetros=Superfície útil (m²):
catalan.DilveTitulo=Compte de DILVE (opcional)
catalan.DilveDesc=Per als suggeriments de compra i l'idioma dels llibres
catalan.DilveAyuda=DILVE és gratuït per a biblioteques: l'usuari i la contrasenya els dona la FGEE. Si encara no els tens, deixa-ho en blanc i escriu-los després a Configuració.
catalan.DilveUsuario=Usuari:
catalan.DilveClave=Contrasenya:
catalan.MarcTitulo=Catàleg MARC (opcional)
catalan.MarcDesc=Per conèixer l'idioma dels llibres antics
catalan.MarcAyuda=Si tens el .db del catàleg (el de la teva xarxa o el que genera conversor.py), tria el fitxer. Bildumargi en prendrà l'idioma dels teus exemplars la primera vegada que analitzis els llistats. Ho pots deixar en blanc.
catalan.MarcFichero=Fitxer .db del catàleg:
catalan.MarcFiltro=Bases de dades (*.db)|*.db|Tots els fitxers|*.*
catalan.NumeroMal=Escriu només números als habitants i la superfície.
catalan.BorrarDatos=Vols esborrar també les dades de Bildumargi (càrregues desades, configuració i fitxes de DILVE)?%n%nSi el reinstal·laràs, tria «No» i les conservaràs.
english.Abrir=Open Bildumargi
english.BibTitulo=Your library
english.BibDesc=Data for the indicators (can be changed later in Settings)
english.BibAyuda=Population gives documents per inhabitant; floor area, documents per m². You can leave it blank.
english.BibNombre=Library name:
english.BibRed=Library network it belongs to (if any):
english.BibPoblacion=Inhabitants served:
english.BibMetros=Usable floor area (m²):
english.DilveTitulo=DILVE account (optional)
english.DilveDesc=For purchase suggestions and the language of books
english.DilveAyuda=DILVE is free for libraries: the FGEE provides the username and password. If you do not have them yet, leave this blank and enter them later in Settings.
english.DilveUsuario=Username:
english.DilveClave=Password:
english.MarcTitulo=MARC catalogue (optional)
english.MarcDesc=To know the language of older books
english.MarcAyuda=If you have the catalogue .db (your network's or one made with conversor.py), choose the file. Bildumargi will take your items' language from it the first time you analyse your lists. You can leave it blank.
english.MarcFichero=Catalogue .db file:
english.MarcFiltro=Databases (*.db)|*.db|All files|*.*
english.NumeroMal=Please use digits only for inhabitants and floor area.
english.BorrarDatos=Also delete Bildumargi's data (saved uploads, settings and DILVE records)?%n%nIf you will reinstall it, choose "No" to keep them.

[Tasks]
Name: "escritorio"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\..\build\windows\dist\Bildumargi\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Bildumargi"; Filename: "{app}\Bildumargi.exe"
Name: "{autodesktop}\Bildumargi"; Filename: "{app}\Bildumargi.exe"; Tasks: escritorio

[Run]
Filename: "{app}\Bildumargi.exe"; Description: "{cm:Abrir}"; Flags: nowait postinstall skipifsilent

[Code]
var
  PaginaBiblioteca, PaginaDilve: TInputQueryWizardPage;
  PaginaMarc: TInputFileWizardPage;

function CarpetaDatos(): String;
begin
  Result := ExpandConstant('{localappdata}\Bildumargi\datos');
end;

{ Si Bildumargi ya está configurado (actualización), no se vuelve a preguntar }
function YaConfigurado(): Boolean;
begin
  Result := FileExists(CarpetaDatos() + '\configuracion.json');
end;

procedure InitializeWizard();
begin
  PaginaBiblioteca := CreateInputQueryPage(wpSelectTasks, CustomMessage('BibTitulo'),
    CustomMessage('BibDesc'), CustomMessage('BibAyuda'));
  PaginaBiblioteca.Add(CustomMessage('BibNombre'), False);
  PaginaBiblioteca.Add(CustomMessage('BibRed'), False);
  PaginaBiblioteca.Add(CustomMessage('BibPoblacion'), False);
  PaginaBiblioteca.Add(CustomMessage('BibMetros'), False);

  PaginaDilve := CreateInputQueryPage(PaginaBiblioteca.ID, CustomMessage('DilveTitulo'),
    CustomMessage('DilveDesc'), CustomMessage('DilveAyuda'));
  PaginaDilve.Add(CustomMessage('DilveUsuario'), False);
  PaginaDilve.Add(CustomMessage('DilveClave'), True);

  PaginaMarc := CreateInputFilePage(PaginaDilve.ID, CustomMessage('MarcTitulo'),
    CustomMessage('MarcDesc'), CustomMessage('MarcAyuda'));
  PaginaMarc.Add(CustomMessage('MarcFichero'), CustomMessage('MarcFiltro'), '.db');
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := YaConfigurado() and
    ((PageID = PaginaBiblioteca.ID) or (PageID = PaginaDilve.ID) or (PageID = PaginaMarc.ID));
end;

function SoloDigitos(Texto: String): Boolean;
var
  I: Integer;
begin
  Result := True;
  for I := 1 to Length(Texto) do
    if Pos(Texto[I], '0123456789.') = 0 then
      Result := False;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if (CurPageID = PaginaBiblioteca.ID) and
     not (SoloDigitos(Trim(PaginaBiblioteca.Values[2])) and SoloDigitos(Trim(PaginaBiblioteca.Values[3]))) then
  begin
    MsgBox(CustomMessage('NumeroMal'), mbError, MB_OK);
    Result := False;
  end;
end;

procedure Apuntar(Fichero, Clave, Valor: String);
begin
  if Trim(Valor) <> '' then
    SetIniString('Bildumargi', Clave, Trim(Valor), Fichero);
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Fichero, Poblacion: String;
begin
  if (CurStep = ssPostInstall) and not YaConfigurado() then
  begin
    ForceDirectories(CarpetaDatos());
    Fichero := CarpetaDatos() + '\instalacion.ini';
    Poblacion := PaginaBiblioteca.Values[2];
    StringChangeEx(Poblacion, '.', '', True);       { «1.102» → «1102» }
    Apuntar(Fichero, 'nombre', PaginaBiblioteca.Values[0]);
    Apuntar(Fichero, 'red', PaginaBiblioteca.Values[1]);
    Apuntar(Fichero, 'poblacion', Poblacion);
    Apuntar(Fichero, 'metros', PaginaBiblioteca.Values[3]);
    Apuntar(Fichero, 'dilve_usuario', PaginaDilve.Values[0]);
    if Trim(PaginaDilve.Values[1]) <> '' then
      SetIniString('Bildumargi', 'dilve_clave', PaginaDilve.Values[1], Fichero);
    Apuntar(Fichero, 'marc', PaginaMarc.Values[0]);
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if (CurUninstallStep = usPostUninstall) and DirExists(CarpetaDatos()) then
    if MsgBox(CustomMessage('BorrarDatos'), mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
      DelTree(ExpandConstant('{localappdata}\Bildumargi'), True, True, True);
end;
