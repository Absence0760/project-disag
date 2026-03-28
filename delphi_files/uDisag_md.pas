{----------------------------------------------------------------------------}
{  Program      :   D i s a g - M D                                          }
{----------------------------------------------------------------------------}
{                                                                            }
{  Description  : Converts monthly flows to daily flows, by dis-             }
{                 aggregation based on a related daily record                }
{                                                                            }
{  Written      : AJ Greyling ............................... Jun 91 [v1.0]  }
{  Modified     : AJ Greyling ............................... Mar 96 [v1.1]  }
{                 - if dailt file not specified, even distrib is assumed.    }
{  Modified     : H Beuster ................................. May 01 [v1.2]  }
{  Modified     : H Beuster ................................. May 07 [v1.3]  }
{                 - patch with daily data from same month, other year        }
{                 - use month with volume closest to target month            }
{                 - Windows version                                          }
{                                                                            }
{  Notes : o  Dates automatically determined                                 }
{                                                                            }
{                                       Qobs(day)                            }
{          o  Qgen(day)  =  Qgen(mon) * ---------                            }
{                                       Qobs(mon)                            }
{          o  if gen flow occurs in a month where obs flow is 0, the gen flow}
{             is distributed evenly through the month                        }
{                                                                            }
{----------------------------------------------------------------------------}
unit uDisag_md ;

interface

uses
   {Crt,}
   uTools, {Util,} uFiles, Dialogs, SysUtils ;

type
  DisagMethodType = (dmOneFile, dmPatchCal, dmPatchFile, dmIncremental, dmEven) ;

const
  version = 1.2 ;

var
  FloObsD : array[1..2] of array of array of Daily_Type ;
  FloGenD :                array of array of Daily_Type ;
  FloGenM :                         array of Monthly_Type ;

  StartYear, StartMonth,
  EndYear,   EndMonth : longint ;
  ncy, nhy : integer;

  NoFiles,nf          : integer ;
  StartObs            : array[1..2] of longint ;
  FileInOD            : array[1..2] of string;
  FileInGM, FileOutGD,
  FileOutRep          : string;
  inOD                : array[1..2] of text ;
  inGM, outGD, rep    : text ;

  UsePartMon          : boolean ;

  DisagMethod         : DisagMethodType ;

function  FindPYear(hy, hm: integer): integer;
procedure Write_FileHeader ;
procedure Set_Files ;
procedure Set_StartDates ;
procedure Convert_Month(y, m: integer) ;
procedure Process ;

{-----------------------------------------------------------------------------}
implementation
{-----------------------------------------------------------------------------}

procedure Write_FileHeader ;
  var
    f, i : integer ;
  begin
    writeln( outGD, Dash80 );
    writeln( outGD, 'Description   : ', ExtractFileName(FileOutGD) );
    writeln( outGD, 'Units         : m3/s' ) ;
    writeln( outGD, 'Disaggregated    (monthly) : ', ExtractFileName(FileinGM) );
    for f := 1 to 2 do
      writeln( outGD, 'Disaggregator,',f,'  (daily  ) : ', ExtractFileName(FileInOD[f]) ) ;

    write( outGD, 'Disag method  : ' ) ;
    case DisagMethod of
      dmEven        : writeln( outGD, 'Even distribution' ) ;
      dmOneFile     : writeln( outGD, 'One disaggregator' ) ;
      dmIncremental : writeln( outGD, 'Distrib with incremental runoff (',
                                     ExtractFileName(FileInOD[1]),' - ',
                                     ExtractFileName(FileInOD[2]),')' ) ;
      dmPatchFile   : writeln( outGD, 'Distrib with ',ExtractFileName(FileInOD[1]),
                                   ', Patched with ',ExtractFileName(FileInOD[2]) ) ;
      dmPatchCal    : writeln( outGD, 'Distrib with ',ExtractFileName(FileInOD[1]),
                                   ', Patched with similar month' ) ;
    end ;

    for i := 4+2 to 7 do writeln( outGD, '-' ) ;
    writeln( outGD, 'Run Date      : ', GetDateTimeString ) ;
    writeln( outGD, dash80 ) ;
    writeln( outGD ) ;
  end ;

{-----------------------------------------------------------------------------}
{  S E T _ F I L E S                                                          }
{-----------------------------------------------------------------------------}

procedure Set_Files ;
  var
    f : integer ;
  begin
    {--- assign }
    for f := 1 to NoFiles do begin
      assign( inOD[f], FileInOD[f] ) ;  reset  ( inOD[f] ) ;
    end ;
    assign  ( inGM,    FileInGM ) ;     reset  ( inGM ) ;
    assign  ( outGD,   FileOutGD );     rewrite( outGD) ;
    assign  ( rep,     FileOutRep);     rewrite( rep  ) ;
  end ;

{-----------------------------------------------------------------------------}
{  S T A R T - D A T E S                                                      }
{-----------------------------------------------------------------------------}

procedure Set_StartDates ;

  var
    f, StartDate, date, sy, sm : longint ;

  begin
    {--- get start dates }
    StartDate := 0 ;
    for f := 1 to NoFiles do begin
      GetFileStartDate( inOD[f], 'D', sy, sm, 12 ) ;
      {--- only use full hydro years}
      if sm > 10 then sy := sy+1 ;
      sm := 10 ;
      StartObs[f] := sy*100+sm ;
    end ;
    StartDate := StartObs[1] ;
    if (DisagMethod = dmIncremental) and (StartObs[2] > StartObs[1])
    then StartDate := StartObs[2] ;

    GetFileStartDate( inGM, 'M', sy, sm, 5 ) ;
    date := (sy{-1900})*100+10 ;
    if (date > StartDate) then StartDate :=date ;
    StartYear := StartDate div 100{ + 1900} ;
    StartMonth:= StartDate - (StartYear{-1900})*100 ;

    {--- set daily files to start - calender }

    if NoFiles > 0 then
      SetFileToStart( inOD[1], FileInOD[1], 'D', StartYear{-1900}, StartMonth, 12 ) ;

    if NoFiles > 1 then begin
      case DisagMethod of
        dmIncremental : sy := StartYear ;
        dmPatchFile   : if StartObs[2] div 100 > StartYear then
                        sy := StartObs[2] div 100 else
                        sy := StartYear ;
      end ;
      SetFileToStart( inOD[2], FileInOD[2], 'D', sy, StartMonth, 12 ) ;
    end ;

    {--- set monthly file to start - hydro }
(**
    if (StartMonth < 10) then sy := StartYear-1
                         else sy := StartYear ;
**)
    SetFileToStart  ( inGM,    FileinGM,    'M', StartYear, 10, 5 ) ;
  end ;

{-----------------------------------------------------------------------------}
{  C O N V E R T _ M O N T H                                                    }
{-----------------------------------------------------------------------------}

function FindPYear(hy, hm: integer): integer;
var
  dv, vmin : real;
  ty, cy, cm, i, j, DIM : integer;
  missing : boolean;
begin
  ty := -1; vmin := 9999.9;
  if FloGenM[hy].v[hm] >= 0 then begin
    {--- find month with complete daily data and volume closest to target month}
    for i := 0 to nhy-2 do begin
       if (FloGenM[i].v[hm] >= 0) and (i <> hy) then begin
         dv := abs(FloGenM[i].v[hm] - FloGenM[hy].v[hm]);
         if dv < vmin then begin
           missing := FALSE;
           {--- calendar year, month}
           if hm > 3 then begin
             cy := i+1;
             cm := hm - 3;
           end else begin
             cy := i;
             cm := hm + 9;
           end;
           DIM := DaysInMonth(cy+StartYear, cm);
           for j := 1 to DIM do if FloObsD[1,cy,cm].v[j] < 0 then
             missing := TRUE;
           if not missing then begin
             ty := cy;
             vmin := dv;
           end;
         end;
       end;
    end;
  end;
  Result := ty;
end;

procedure Convert_Month(y, m: integer) ;

  var
    d, DIM, f, hm, hy, cy, py, pm : integer ;
    q, qM, f1, f2, f3 : real ;
    qD            : array[1..31] of real ;
    missing       : boolean ;

  begin
(**)
    cy := y - StartYear;
    if m > 9 then hy := cy else hy := cy - 1;
    py := -1;

    {--- Hydro month (hm), # Days }
    hm := m+3 ;
    if (hm > 12) then dec(hm,12) ;
    {DIM := DaysinMonth( FloObsD[1].year, FloObsD[1].month ) ;}
    DIM := DaysinMonth( y, m ) ;

    {--- daily data missing }
    missing := FALSE ;
    case DisagMethod of
      dmEven        : ;
      dmOneFile     : for d := 1 to DIM do
                      IF (FloObsD[1,cy,m].v[d]<0) then
                        missing := TRUE ;
      dmIncremental : for d := 1 to DIM do
                      IF (FloObsD[1,cy,m].v[d]<0) OR  (FloObsD[nf,cy,m].v[d]<0) then
                        missing := TRUE ;
      dmPatchFile   : for d := 1 to DIM do
                      IF (FloObsD[1,cy,m].v[d]<0) AND (FloObsD[nf,cy,m].v[d]<0) then
                        missing := TRUE ;
      dmPatchCal    : begin
                        for d := 1 to DIM do
                        IF (FloObsD[1,cy,m].v[d]<0) then
                          missing := TRUE ;
                        IF missing then begin
                          py := FindPYear(hy, hm);
                          if py >= 0 then begin
                            missing := FALSE;
                            writeln(rep,FloObsD[1,cy,m].year:4, FloObsD[1,cy,m].month:3,
                            ' Observed daily flow < 0,   Patched with ',
                            py+StartYear:4, FloObsD[1,cy,m].month:3) ;
                          end;
                        end;
                      end;
    end ;

    {--- monthly data missing }
    IF (FloGenM[hy].v[hm] < 0) then
      missing := TRUE ;

    IF missing then for d := 1 to DIM do
      FloGenD[cy,m].v[d] := -99.99
    {--- set qM & qD [1..31] }
    ELSE begin
      {--- sum daily values}
      qM := 0 ;
      IF (DisagMethod = dmEven) then begin
        qm := DIM ;
        for d := 1 to DIM do qD[d] := 1 ;
      END
      ELSE for d := 1 to DIM do begin
        f1 := FloObsD[1,cy,m].v[d] ;
        if nf=2 then
          f2 := FloObsD[2,cy,m].v[d] else f2 := -999.99 ;
        if (DisagMethod = dmPatchCal) then begin
          if py >= 0 then
            f3 := FloObsD[1,py,m].v[d] else f3 := -999.99 ;
        end;
{
        if (f1 < 0) AND (f2 < 0) then begin
          writeln( '*** -ve value in daily file 1 : ', FileInOD[1],', run halted.' ) ;
          writeln(rep,'Error ! -ve value in daily file 1 : ', FileInOD[1],', run halted.' ) ;
          Halt ;
        end ;
}
        case DisagMethod of
          dmOneFile     : qD[d] := f1 ;
          dmIncremental : qD[d] := f1 - f2 ;
          dmPatchFile   : if f1 < 0 then qD[d] := f2
                                    else qD[d] := f1;
          dmPatchCal    : if f1 < 0 then qD[d] := f3
                                    else qD[d] := f1;
        end ;
        if (qD[d] < 0) then qD[d] := 0 ;
        qM := qM + qD[d] ;
      END ;

      {--- set qM & qD, if qM <= 0 }
      if (qM <= 0) and (FloGenM[hy].v[hm] > 0) then begin
        //write('*** observed monthly flow <= 0') ;
        writeln(rep,FloObsD[1,cy,m].year:4, FloObsD[1,cy,m].month:3,' Observed monthly flow <= 0,   Gen Flow= ',
                     FloGenM[hy].v[hm]:7:3) ;
        for d := 1 to dim do
          qD[d] := 1 ;
        qM := dim ;
      end ;

      {--- calc qGenD }
      for d := 1 to dim do begin
        if (qM > 0) then q := FloGenM[hy].v[hm] * qD[d] / qM
                    else q := 0 ;
        FloGenD[cy,m].v[d] := q * 1e6/24/3600 ;                              {**** Mm3/d --> m3/s}
      end ;
    END ;

    {--- set results }
{
    FloGenD.year  := FloObsD[1].year ;
    FloGenD.month := FloObsD[1].month ;
}
    FloGenD[cy,m].year  := y ;
    FloGenD[cy,m].month := m ;
    WriteDailyData( outGD, FloGenD[cy,m] ) ;
(**)
  end ;

{-----------------------------------------------------------------------------}
{  P R O C E S S                                                              }
{-----------------------------------------------------------------------------}

procedure Process ;

  var
    f     : integer ;
    FIN   : boolean ;
    Error : boolean ;
    year, month  : longint ;
    cdate, edate : longint ;

  begin
    year  := StartYear ;
    month := StartMonth ;
    ncy := 1; {calendar years}
    nhy := 1; {hydro years}
    SetLength(FloGenM, nhy);
    ReadMonthlyData( inGM, FloGenM[nhy-1] ) ;
    SetLength(FloGenD,ncy,13);
    for f := 1 to 2 do
      SetLength(FloObsD[f],ncy,13);

    REPEAT
      cdate := year*100 + month ;
      case DisagMethod of
        dmIncremental : nf := 2 ;
        dmPatchFile   : if cdate < StartObs[2] then nf := 1 else nf := 2 ;
        dmOneFile, dmPatchCal : nf := 1 ;
      end ;
      for f := 1 to nf do begin
        ReadDailyData( inOD[f], FloObsD[f,ncy-1,month] ) ;
      end;

      {--- check alignment of data files }
      if (month = 10) then begin
        error := false ;
        for f := 1 to nf do
          if (year  <> FloObsD[f,ncy-1,month].year{+1900}) OR
             (month <> FloObsD[f,ncy-1,month].month)then
            error := true ;
        if (year <> FloGenM[nhy-1].year) then error := true ;
        if (error = true) then begin
          ShowMessage('ERROR ! Years do not align; year=' + inttostr(year) ) ;
          halt ;
        end ;
      end ;

      {--- check EOF }
      FIN := false ;
      for f := 1 to NoFiles do if EOF(inOD[f]) then FIN := true ;
      if EOF(inGM) AND (month = 9)             then FIN := true ;

      {--- inc month }
      if not FIN then begin
        uTools.IncMonth( year, month ) ;
        if (month = 10) then begin
          inc(nhy);
          SetLength(FloGenM, nhy);
          ReadMonthlyData( inGM, FloGenM[nhy-1] ) ;
        end;
        if (month = 1) then begin
          inc(ncy);
          SetLength(FloGenD,ncy,13);
          for f := 1 to 2 do
            SetLength(FloObsD[f],ncy,13);
        end;
      end ;
    UNTIL FIN ;

    EndYear := year;
    EndMonth := month;

    edate := EndYear*100 + EndMonth ;
    year  := StartYear ;
    month := StartMonth ;
    cdate := year*100 + month ;
    WHILE cdate <= edate do begin
      Convert_Month(year, month);
      uTools.IncMonth( year, month ) ;
      cdate := year*100 + month ;
    END;

    SetLength(FloGenD, 0);
    SetLength(FloGenM, 0);
    for f := 1 to 2 do
      SetLength(FloObsD[f], 0);
  end ;

{-----------------------------------------------------------------------------}
end.
{-----------------------------------------------------------------------------}
