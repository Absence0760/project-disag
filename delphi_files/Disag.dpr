program Disag;

uses
  Forms,
  uTools in 'uTools.pas',
  uDisag_md in 'uDisag_md.pas',
  uFiles in 'uFiles.pas',
  uMain in 'uMain.pas' {frmMain};

{$R *.res}

begin
  Application.Initialize;
  Application.CreateForm(TfrmMain, frmMain);
  Application.Run;
end.
