unit uMain;

interface

uses
  Windows, Messages, SysUtils, Variants, Classes, Graphics, Controls, Forms,
  Dialogs, StdCtrls, Buttons, ExtCtrls, uFiles, DateUtils;

type
  TfrmMain = class(TForm)
    OpenDialog1: TOpenDialog;
    SaveDialog1: TSaveDialog;
    btnDisag: TBitBtn;
    BitBtn2: TBitBtn;
    GroupBox1: TGroupBox;
    edMon: TLabeledEdit;
    edDay1: TLabeledEdit;
    btnMon: TSpeedButton;
    btnDay1: TSpeedButton;
    edDay2: TLabeledEdit;
    btnDay2: TSpeedButton;
    edDayOut: TLabeledEdit;
    edRep: TLabeledEdit;
    rgMethod: TRadioGroup;
    btnDayOut: TSpeedButton;
    btnRep: TSpeedButton;
    procedure btnFileInClick(Sender: TObject);
    procedure BitBtn2Click(Sender: TObject);
    procedure btnDisagClick(Sender: TObject);
    procedure rgMethodClick(Sender: TObject);
    procedure FormShow(Sender: TObject);
    procedure btnDayOutClick(Sender: TObject);
    procedure btnRepClick(Sender: TObject);
  private
    { Private declarations }
    cdir : string;
    dataD : Daily_Type ;
    dataM : Monthly_Type ;
    StartYear, EndYear, NoYears : integer ;
    procedure SetControls;
  public
    { Public declarations }
  end;

const
  l   = 8 ;
  w   = 2 ;
  nhl = 2 ;

var
  frmMain: TfrmMain;

implementation

{$R *.dfm}
uses
 uDisag_md;

{-----------------------------------------------------------------------------}
{  Create, Show, etc
{-----------------------------------------------------------------------------}
procedure TfrmMain.FormShow(Sender: TObject);
begin
  cdir := GetCurrentDir;
  rgMethod.ItemIndex := 0;
  SetControls;
end;

{-----------------------------------------------------------------------------}
{  Misc
{-----------------------------------------------------------------------------}

procedure TfrmMain.SetControls;
var
  ok: boolean;
begin
  ok := FileExists(edMon.Text);
  case rgMethod.ItemIndex of
    0,1: begin {disag with 1 daily file}
           edDay1.Enabled := true; edDay1.Color := clWindow;
           edDay2.Enabled := false; edDay2.Color := clBtnFace;
           btnDay1.Enabled := true; btnDay2.Enabled := false;
           ok := ok AND FileExists(edDay1.Text);
         end;
    2,3: begin {disag with daily file1, patch with file 2}
           edDay1.Enabled := true; edDay1.Color := clWindow;
           edDay2.Enabled := true; edDay2.Color := clWindow;
           btnDay1.Enabled := true; btnDay2.Enabled := true;
           ok := ok AND FileExists(edDay1.Text);
           ok := ok AND FileExists(edDay2.Text);
         end;
    4  : begin {disag with even distrib}
           edDay1.Enabled := false; edDay1.Color := clBtnFace;
           edDay2.Enabled := false; edDay2.Color := clBtnFace;
           btnDay1.Enabled := false; btnDay2.Enabled := false;
         end;
  end;
  ok := ok AND DirectoryExists(ExtractFilePath(edDayOut.Text));
  ok := ok and (length(ExtractFileName(edDayOut.Text)) > 0);
  ok := ok AND DirectoryExists(ExtractFilePath(edRep.Text));
  ok := ok and (length(ExtractFileName(edRep.Text)) > 0);
  btnDisag.Enabled := ok;
end;

{-----------------------------------------------------------------------------}
{  Events
{-----------------------------------------------------------------------------}
procedure TfrmMain.rgMethodClick(Sender: TObject);
begin
  SetControls;
end;

procedure TfrmMain.btnFileInClick(Sender: TObject);
var
  s : string;
begin
  OpenDialog1.FileName := '';
  OpenDialog1.InitialDir := cdir;
  s := 'All files (*.*)|*.*';
  if (Sender = btnMon) then
    s := 'NS monthly flow files (*.mon,*.nat,*.cur)|*.mon;*.nat;*.cur';
  if (Sender = btnDay1) or (Sender = btnDay2) then
    s := 'NS daily flow files (*.day)|*.day';
  OpenDialog1.Filter := s;
  if OpenDialog1.Execute then begin
    s := OpenDialog1.FileName;
    if Sender = btnMon then begin
      edMon.Text := s;
      {--- set output file names}
      if length(edDayOut.Text) = 0 then edDayOut.Text := ChangeFileExt(s,'.day');
      if length(edRep.Text) = 0 then edRep.Text := ChangeFileExt(s,'.rep');
    end;
    if Sender = btnDay1 then edDay1.Text := s;
    if Sender = btnDay2 then edDay2.Text := s;
    cdir := ExtractFilePath(s);
    SetControls;
  end;
end;

procedure TfrmMain.btnDayOutClick(Sender: TObject);
var
  s : string;
begin
  SaveDialog1.FileName := '';
  SaveDialog1.InitialDir := cdir;
  SaveDialog1.Filter := 'NS daily flow files (*.day)|*.day';
  if SaveDialog1.Execute then begin
    s := SaveDialog1.FileName;
    edDayOut.Text := s;
    cdir := ExtractFilePath(s);
    SetControls;
  end;
end;

procedure TfrmMain.btnRepClick(Sender: TObject);
var
  s : string;
begin
  SaveDialog1.FileName := '';
  SaveDialog1.InitialDir := cdir;
  SaveDialog1.Filter := 'Text report file (*.rep)|*.rep';
  if SaveDialog1.Execute then begin
    s := SaveDialog1.FileName;
    edRep.Text := s;
    cdir := ExtractFilePath(s);
    SetControls;
  end;
end;

procedure TfrmMain.BitBtn2Click(Sender: TObject);
begin
  Close;
end;

procedure TfrmMain.btnDisagClick(Sender: TObject);
var
  f : integer;
  s : string;
begin
  try
    {--- set parameters}
    DisagMethod := DisagMethodType(rgMethod.ItemIndex);

    {--- file names }
    FileInOD[1] := edDay1.Text;
    FileInOD[2] := edDay2.Text;
    FileinGM    := edMon.Text;
    FileOutGD   := edDayOut.Text;
    FileOutRep  := edRep.Text;

    NoFiles := 0;
    case DisagMethod of
      dmOneFile, dmPatchCal :
        NoFiles := 1;
      dmPatchFile, dmIncremental :
        NoFiles := 2;
    end;

    Set_Files;
    Set_StartDates ;
    Write_FileHeader ;
    Process ;

    for f := 1 to NoFiles do CloseFile( inOD[f] ) ;
    CloseFile(inGM) ;
    CloseFile(outGD) ;
    CloseFile(rep) ;
    ShowMessage('Done!');
  except;
    ShowMessage('Done, with error(s)!');
  end;
end;

end.
