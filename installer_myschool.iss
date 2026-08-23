; MySchoolGN - Inno Setup Installer Script
; ==========================================
; Auteur  : GS Hadja Kanfing Dian
; Version : voir MyAppVersion ci-dessous (recopie depuis ecole_moderne/version.py
; par build_exe.py : un seul numero a modifier, jamais deux a garder d'accord)
;
; Prérequis : Inno Setup 6+ (https://jrsoftware.org/isinfo.php)
;
; Pour compiler :
;   1. Installez Inno Setup
;   2. Ouvrez ce fichier dans Inno Setup Compiler
;   3. Appuyez sur Ctrl+F9 (Compile)
;   4. L'installateur est créé dans le dossier "Output"
;
; Supporte :
;   - Installation fraîche
;   - Mise à jour (préserve base de données, médias et synchronisation)

#define MyAppVersion "1.2.1"

[Setup]
; ── Identification ─────────────────────────────────────────────────────────────
AppId={{B7E4A2D1-F3C8-4B91-A5E6-GS2024HADJA01}
AppName=MySchoolGN
AppVersion={#MyAppVersion}
AppVerName=MySchoolGN {#MyAppVersion}
AppPublisher=GS Hadja Kanfing Dian
AppPublisherURL=https://www.lesjardinswosewa.com
AppSupportURL=https://www.lesjardinswosewa.com
AppCopyright=Copyright © 2024 GS Hadja Kanfing Dian. Tous droits réservés.

; ── Installation ───────────────────────────────────────────────────────────────
DefaultDirName={autopf}\MySchoolGN
DefaultGroupName=MySchoolGN
AllowNoIcons=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

; Fermeture automatique de l application avant mise a jour
CloseApplications=force
RestartApplications=no

; ── Sortie ─────────────────────────────────────────────────────────────────────
OutputDir=Output
OutputBaseFilename=MySchoolGN_Setup_v{#MyAppVersion}_Generic

; ── Icône et splash ────────────────────────────────────────────────────────────
SetupIconFile=myschool.ico

; ── Compression ────────────────────────────────────────────────────────────────
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes

; ── Interface ──────────────────────────────────────────────────────────────────
WizardStyle=modern
WizardSizePercent=120
DisableWelcomePage=no

; ── Désinstallation ────────────────────────────────────────────────────────────
UninstallDisplayName=MySchoolGN - Système de Gestion Scolaire
UninstallDisplayIcon={autopf}\MySchoolGN\MySchoolGN.exe
CreateUninstallRegKey=yes

; ── Version info (visible dans Programmes et fonctionnalités) ──────────────────
VersionInfoVersion={#MyAppVersion}.0
VersionInfoCompany=GS Hadja Kanfing Dian
VersionInfoDescription=MySchoolGN - Système de Gestion Scolaire
VersionInfoCopyright=Copyright © 2024 GS Hadja Kanfing Dian

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon";   Description: "Créer un raccourci sur le Bureau";         GroupDescription: "Raccourcis :"
Name: "startmenuicon"; Description: "Créer une entrée dans le menu Démarrer";   GroupDescription: "Raccourcis :"
Name: "autostart";     Description: "Lancer MySchoolGN au démarrage de Windows"; GroupDescription: "Options :";   Flags: unchecked

[Files]
; Application compilée (tout le dossier dist\MySchoolGN)
Source: "dist\MySchoolGN\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; Script de désinstallation
Source: "desinstaller.bat"; DestDir: "{app}"; Flags: ignoreversion

; Script d'arrêt du serveur (raccourci menu Démarrer)
Source: "Arreter_MySchoolGN.bat"; DestDir: "{app}"; Flags: ignoreversion

; Icône
Source: "myschool.ico"; DestDir: "{app}"; Flags: ignoreversion

; Modèle de configuration de synchronisation en ligne (à renseigner par le technicien)
Source: "sync_config.example.json"; DestDir: "{app}"; Flags: ignoreversion

[Dirs]
; Dossiers avec permissions d'écriture
Name: "{app}\logs";                 Permissions: users-modify
Name: "{app}\media";                Permissions: users-modify
Name: "{app}\media\photos_eleves";  Permissions: users-modify
Name: "{app}\media\logos_ecoles";   Permissions: users-modify
Name: "{app}\backups";              Permissions: users-modify
Name: "{app}\staticfiles";          Permissions: users-modify

[Icons]
; Bureau
Name: "{autodesktop}\MySchoolGN"; Filename: "{app}\MySchoolGN.exe"; WorkingDir: "{app}"; IconFilename: "{app}\myschool.ico"; Comment: "MySchoolGN - Système de Gestion Scolaire"; Tasks: desktopicon

; Menu Démarrer
Name: "{group}\MySchoolGN";                        Filename: "{app}\MySchoolGN.exe";         WorkingDir: "{app}"; IconFilename: "{app}\myschool.ico"; Comment: "Démarrer MySchoolGN"
Name: "{group}\Arrêter MySchoolGN";                Filename: "{app}\Arreter_MySchoolGN.bat"; WorkingDir: "{app}"; Comment: "Arrêter le serveur MySchoolGN"
Name: "{group}\{cm:UninstallProgram,MySchoolGN}";  Filename: "{uninstallexe}"

; Démarrage automatique (optionnel)
Name: "{userstartup}\MySchoolGN"; Filename: "{app}\MySchoolGN.exe"; WorkingDir: "{app}"; Tasks: autostart

[Registry]
; Enregistrement pour le panneau "Programmes et fonctionnalités"
Root: HKCU; Subkey: "Software\GS Hadja Kanfing Dian\MySchoolGN"; ValueType: string; ValueName: "Version";    ValueData: "{#MyAppVersion}"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\GS Hadja Kanfing Dian\MySchoolGN"; ValueType: string; ValueName: "InstallDir"; ValueData: "{app}";  Flags: uninsdeletevalue

[Run]
; Proposer de lancer l'application après installation
Filename: "{app}\MySchoolGN.exe"; Description: "Démarrer MySchoolGN maintenant"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent

; Mise a jour automatique : l'application s'est arretee elle-meme pour se
; laisser remplacer, et l'installation est silencieuse. Sans cette ligne,
; l'utilisateur qui vient de lancer MySchoolGN ne verrait jamais sa fenetre
; s'ouvrir. L'entree ci-dessus, elle, est ignoree en mode silencieux.
Filename: "{app}\MySchoolGN.exe"; WorkingDir: "{app}"; Flags: nowait; Check: RelanceDemandee

[UninstallRun]
; Arrêter le serveur avant la désinstallation
Filename: "taskkill"; Parameters: "/F /IM MySchoolGN.exe"; Flags: runhidden; RunOnceId: "KillServer"

[UninstallDelete]
Type: filesandordirs; Name: "{app}\logs"
Type: filesandordirs; Name: "{app}\staticfiles"
Type: filesandordirs; Name: "{app}\__pycache__"
Type: files;          Name: "{app}\.secret_key"
Type: files;          Name: "{app}\install_path.txt"

[Messages]
WelcomeLabel1=Bienvenue dans l'assistant d'installation de MySchoolGN
WelcomeLabel2=Ce programme va installer MySchoolGN - Système de Gestion Scolaire sur votre ordinateur.%n%nMySchoolGN est une solution complète de gestion scolaire développée par GS Hadja Kanfing Dian. Elle fonctionne entièrement hors ligne.%n%nFermez toutes les autres applications avant de continuer.
FinishedHeadingLabel=Installation de MySchoolGN terminée !
FinishedLabel=MySchoolGN a été installé avec succès sur votre ordinateur.%n%nIdentifiants par défaut :%n  Utilisateur : admin%n  Mot de passe  : admin1234%n%nL'application fonctionne hors ligne et synchronise automatiquement les données avec www.lesjardinswosewa.com lorsque la connexion Internet est disponible.

[Code]

// ──────────────────────────────────────────────────────────────────────────────
// Variables globales pour la gestion des mises à jour
// ──────────────────────────────────────────────────────────────────────────────
var
  IsUpdate: Boolean;
  BackupTempDir: String;

// ── Détection si c'est une mise à jour ───────────────────────────────────────
function IsUpgradeInstall(): Boolean;
var
  ExePath: String;
begin
  ExePath := WizardDirValue + '\MySchoolGN.exe';
  Result := FileExists(ExePath);
end;

// ── Arrêter l'application si elle est en cours d'exécution ───────────────────
procedure KillRunningApp();
var
  ResultCode: Integer;
begin
  Exec('taskkill', '/F /IM MySchoolGN.exe /T', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Sleep(500);
end;

// ── Copier un fichier vers le dossier de sauvegarde temporaire ───────────────
procedure BackupFile(const FileName: String);
var
  SrcPath, DstPath: String;
begin
  SrcPath := ExpandConstant('{app}\') + FileName;
  DstPath := BackupTempDir + '\' + FileName;
  if FileExists(SrcPath) then
  begin
    Log('Sauvegarde : ' + FileName);
    CopyFile(SrcPath, DstPath, False);
  end;
end;

// ── Restaurer un fichier depuis le dossier de sauvegarde temporaire ──────────
procedure RestoreFile(const FileName: String);
var
  SrcPath, DstPath: String;
begin
  SrcPath := BackupTempDir + '\' + FileName;
  DstPath := ExpandConstant('{app}\') + FileName;
  if FileExists(SrcPath) then
  begin
    Log('Restauration : ' + FileName);
    CopyFile(SrcPath, DstPath, False);
  end;
end;

// ── Copier récursivement un dossier ──────────────────────────────────────────
procedure BackupDirectory(const DirName: String);
var
  SrcDir, DstDir: String;
  FindRec: TFindRec;
begin
  SrcDir := ExpandConstant('{app}\') + DirName;
  DstDir := BackupTempDir + '\' + DirName;
  if DirExists(SrcDir) then
  begin
    Log('Sauvegarde dossier : ' + DirName);
    ForceDirectories(DstDir);
    if FindFirst(SrcDir + '\*', FindRec) then
    try
      repeat
        if (FindRec.Name <> '.') and (FindRec.Name <> '..') then
        begin
          if (FindRec.Attributes and FILE_ATTRIBUTE_DIRECTORY) <> 0 then
            BackupDirectory(DirName + '\' + FindRec.Name)
          else
            CopyFile(SrcDir + '\' + FindRec.Name, DstDir + '\' + FindRec.Name, False);
        end;
      until not FindNext(FindRec);
    finally
      FindClose(FindRec);
    end;
  end;
end;

// ── Restaurer récursivement un dossier ───────────────────────────────────────
procedure RestoreDirectory(const DirName: String);
var
  SrcDir, DstDir: String;
  FindRec: TFindRec;
begin
  SrcDir := BackupTempDir + '\' + DirName;
  DstDir := ExpandConstant('{app}\') + DirName;
  if DirExists(SrcDir) then
  begin
    Log('Restauration dossier : ' + DirName);
    ForceDirectories(DstDir);
    if FindFirst(SrcDir + '\*', FindRec) then
    try
      repeat
        if (FindRec.Name <> '.') and (FindRec.Name <> '..') then
        begin
          if (FindRec.Attributes and FILE_ATTRIBUTE_DIRECTORY) <> 0 then
            RestoreDirectory(DirName + '\' + FindRec.Name)
          else
            CopyFile(SrcDir + '\' + FindRec.Name, DstDir + '\' + FindRec.Name, False);
        end;
      until not FindNext(FindRec);
    finally
      FindClose(FindRec);
    end;
  end;
end;

// ── Supprimer récursivement un dossier temporaire ────────────────────────────
procedure CleanupBackupDir();
begin
  if DirExists(BackupTempDir) then
    DelTree(BackupTempDir, True, True, True);
end;

// ── Sauvegarde des données utilisateur avant l'installation ──────────────────
procedure BackupUserData();
var
  FindRec: TFindRec;
  AppDir: String;
begin
  BackupTempDir := ExpandConstant('{tmp}\MySchoolGN_UpdateBackup');
  ForceDirectories(BackupTempDir);

  // Fichiers de données critiques
  BackupFile('db.sqlite3');
  BackupFile('.secret_key');
  BackupFile('.trial_start');
  BackupFile('.env');
  BackupFile('license.dat');
  BackupFile('sync_config.json');
  BackupFile('.sync_state.json');

  // Tous les fichiers de licence (license_*.lic)
  AppDir := ExpandConstant('{app}\');
  if FindFirst(AppDir + 'license_*.lic', FindRec) then
  try
    repeat
      BackupFile(FindRec.Name);
    until not FindNext(FindRec);
  finally
    FindClose(FindRec);
  end;

  // Dossier media (photos élèves, logos écoles, etc.)
  BackupDirectory('media');

  // Dossier backups
  BackupDirectory('backups');

  // Dossier logs
  BackupDirectory('logs');
end;

// ── Restauration des données utilisateur après l'installation ────────────────
procedure RestoreUserData();
var
  FindRec: TFindRec;
begin
  // Fichiers de données critiques
  RestoreFile('db.sqlite3');
  RestoreFile('.secret_key');
  RestoreFile('.trial_start');
  RestoreFile('.env');
  RestoreFile('license.dat');
  RestoreFile('sync_config.json');
  RestoreFile('.sync_state.json');

  // Restaurer tous les fichiers de licence
  if FindFirst(BackupTempDir + '\license_*.lic', FindRec) then
  try
    repeat
      RestoreFile(FindRec.Name);
    until not FindNext(FindRec);
  finally
    FindClose(FindRec);
  end;

  // Restaurer le dossier media
  RestoreDirectory('media');

  // Restaurer le dossier backups
  RestoreDirectory('backups');

  // Restaurer le dossier logs
  RestoreDirectory('logs');

  // Nettoyage du dossier temporaire
  CleanupBackupDir();
end;

// ── Configuration personnalisée placée à côté de l'installateur ─────────────
procedure InstallExternalSyncConfig();
var
  SourceFile: String;
  DestFile: String;
begin
  SourceFile := ExpandConstant('{src}\sync_config.json');
  if not FileExists(SourceFile) then
  begin
    Log('Aucune configuration externe de synchronisation détectée.');
    Exit;
  end;

  DestFile := ExpandConstant('{app}\sync_config.json');
  if CopyFile(SourceFile, DestFile, False) then
    Log('Configuration de synchronisation personnalisée installée.')
  else
    Log('ERREUR : impossible d''installer la configuration de synchronisation personnalisée.');
end;

// ── Relance apres une mise a jour automatique ────────────────────────────────
// Le poste lance l'installateur avec /RELANCE=1 lorsqu'il s'est arrete de
// lui-meme pour installer une nouvelle version.
function RelanceDemandee(): Boolean;
begin
  Result := ExpandConstant('{param:RELANCE|0}') = '1';
end;

// ── Adapter les messages selon le mode (installation / mise à jour) ──────────
procedure CurPageChanged(CurPageID: Integer);
var
  WelcomeMsg: String;
  FinishedMsg: String;
begin
  if CurPageID = wpWelcome then
  begin
    IsUpdate := IsUpgradeInstall();
    if IsUpdate then
    begin
      WizardForm.WelcomeLabel1.Caption := 'Mise à jour de MySchoolGN';
      WelcomeMsg := 'Ce programme va mettre à jour MySchoolGN vers la version {#MyAppVersion} sur votre ordinateur.' + #13#10 + #13#10 +
        'Vos données seront automatiquement préservées :' + #13#10 +
        '  • Base de données (élèves, notes, etc.)' + #13#10 +
        '  • Configuration de synchronisation' + #13#10 +
        '  • Photos et médias' + #13#10 +
        '  • Sauvegardes' + #13#10 + #13#10 +
        'L''application sera fermée automatiquement pendant la mise à jour.' + #13#10 + #13#10 +
        'Cliquez sur Suivant pour continuer.';
      WizardForm.WelcomeLabel2.Caption := WelcomeMsg;
    end;
  end;

  if CurPageID = wpFinished then
  begin
    if IsUpdate then
    begin
      WizardForm.FinishedHeadingLabel.Caption := 'Mise à jour de MySchoolGN terminée !';
      FinishedMsg := 'MySchoolGN a été mis à jour avec succès.' + #13#10 + #13#10 +
        'Toutes vos données ont été préservées :' + #13#10 +
        '  • Base de données intacte' + #13#10 +
        '  • Synchronisation conservée' + #13#10 +
        '  • Photos et médias restaurés' + #13#10 + #13#10 +
        'L''application s''ouvre dans votre navigateur sur http://127.0.0.1:8000';
      WizardForm.FinishedLabel.Caption := FinishedMsg;
    end;
  end;
end;

// ── Étapes d'installation : sauvegarde avant, restauration après ─────────────
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
  begin
    if IsUpdate then
    begin
      Log('=== Mode Mise à jour détecté ===');
      // Arrêter l'application
      KillRunningApp();
      // Sauvegarder les données utilisateur
      BackupUserData();
      Log('Sauvegarde des données terminée.');
    end;
  end;

  if CurStep = ssPostInstall then
  begin
    if IsUpdate then
    begin
      Log('Restauration des données utilisateur...');
      RestoreUserData();
      Log('Restauration terminée. Mise à jour réussie.');
    end;
    // Le fichier téléchargé depuis la fiche école remplace volontairement la
    // configuration intégrée, y compris lors d'une reconfiguration du poste.
    InstallExternalSyncConfig();
  end;
end;

// ── Sauvegarde de la base de données avant désinstallation ───────────────────
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DbPath:     String;
  BackupDir:  String;
  BackupPath: String;
begin
  if CurUninstallStep = usUninstall then
  begin
    DbPath := ExpandConstant('{app}\db.sqlite3');
    if FileExists(DbPath) then
    begin
      if MsgBox(
        'Voulez-vous sauvegarder votre base de données avant la désinstallation ?' + #13#10 + #13#10 +
        'La sauvegarde sera placée dans :' + #13#10 +
        ExpandConstant('{userdocs}\MySchoolGN_Backup'),
        mbConfirmation, MB_YESNO
      ) = IDYES then
      begin
        BackupDir  := ExpandConstant('{userdocs}\MySchoolGN_Backup');
        ForceDirectories(BackupDir);
        BackupPath := BackupDir + '\db_backup_' +
                      GetDateTimeString('yyyymmdd_hhnnss', #0, #0) + '.sqlite3';
        CopyFile(DbPath, BackupPath, False);
        MsgBox(
          'Base de données sauvegardée dans :' + #13#10 + BackupPath,
          mbInformation, MB_OK
        );
      end;
    end;
  end;
end;

// ── Message de fin avec ID machine ───────────────────────────────────────────
function UpdateReadyMemo(Space, NewLine, MemoUserInfoInfo, MemoDirInfo,
  MemoTypeInfo, MemoComponentsInfo, MemoGroupInfo, MemoTasksInfo: String): String;
begin
  if IsUpdate then
  begin
    Result := '═══ MISE À JOUR ═══' + NewLine + NewLine +
              MemoDirInfo + NewLine + NewLine +
              MemoGroupInfo + NewLine + NewLine +
              MemoTasksInfo + NewLine + NewLine +
              '─────────────────────────────────────────' + NewLine +
              'DONNÉES PRÉSERVÉES' + NewLine +
              'Les données suivantes seront automatiquement préservées :' + NewLine +
              '  • Base de données (db.sqlite3)' + NewLine +
              '  • Configuration de synchronisation' + NewLine +
              '  • Photos et médias' + NewLine +
              '  • Sauvegardes' + NewLine +
              '  • Configuration (.secret_key, .env)' + NewLine +
              '─────────────────────────────────────────';
  end
  else
  begin
    Result := MemoDirInfo + NewLine + NewLine +
              MemoGroupInfo + NewLine + NewLine +
              MemoTasksInfo + NewLine + NewLine +
              '─────────────────────────────────────────' + NewLine +
              'SYNCHRONISATION AUTOMATIQUE' + NewLine +
              'MySchoolGN fonctionne hors ligne et synchronise automatiquement' + NewLine +
              'les données dès que la connexion Internet est disponible.' + NewLine +
              '─────────────────────────────────────────';
  end;
end;
