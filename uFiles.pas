{----------------------------------------------------------------------------}
{  U n i t    : F i l e s                                                    }
{----------------------------------------------------------------------------}
{                                                                            }
{ Description : Routines for data files in standard format                   }
{                                                                            }
{ Written     : AJ Greyling ................................ .. Dec 89 [1.0] }
{                                                                            }
{ Modified    : H Beuster ..................................... Jun 05 [1.1] }
{                                                                            }
{ Notes :  [1.1] Modified for use with Delphi.  Added parse procedure.       }
{                                                                            }
{----------------------------------------------------------------------------}
Unit uFiles ;

interface

uses  Controls, DateUtils;


{----- input data arrays }
type
  Monthly_Type = record
                   year             : integer ;
                   v                : array[1..12] of real ;
                 end ;
  Daily_Type   = record
                   year, month      : integer ;
                   v                : array[1..31] of real ;
                   total            : double ;
                 end ;
  Hourly_Type  = record
                   year, month, day : integer ;
                   v                : array[1..24] of real ;
                 end ;
  Min6_Type    = record
                   year, month, day : integer ;
                   v                : array[1..24,1..10] of real ;
                 end ;

  str12 = string[12];

{----- functions }

function Parse(s:string; var date: TDate; var v : real) : integer;
procedure Write_Header(var f : textfile) ;
procedure Write_Data(var f : textfile; data : Daily_Type) ;

procedure ReadMin6Data   ( var f : text ; var d : Min6_Type   ) ;
procedure ReadHourlyData ( var f : text ; var d : Hourly_Type ) ;
procedure ReadDailyData  ( var f : text ; var d : Daily_Type  ) ;
procedure ReadMonthlyData( var f : text ; var d : Monthly_Type) ;

procedure WriteDailyData ( var f : text ; var d : Daily_Type  ) ;
procedure WriteHourlyData( var f : text ; var d : Hourly_Type ) ;

procedure SetFileToStart ( var f : text; s : str12; t : char;
                                             sy, sm   : longint;
                                             nhl      : word    ) ;
procedure GetFileStartDate(var f : text;            t : char;
                                         var sy, sm   : longint;
                                             nhl      : word    ) ;

procedure ZeroMin6Data   ( var d : Min6_Type   ) ;
procedure ZeroHourlyData ( var d : Hourly_Type ) ;
procedure ZeroDailyData  ( var d : Daily_Type  ) ;
procedure ZeroMonthlyData( var d : Monthly_Type) ;

{----------------------------------------------------------------------------}
 IMPLEMENTATION
{----------------------------------------------------------------------------}

uses
  Dialogs, SysUtils;

function Parse(s:string; var date: TDate; var v : real) : integer;
var
  ss : string;
  c,r,y,m,d : integer;
begin
  try
    ss := Copy(s,0,4);
    y := strtoint(ss);
    ss := Copy(s,5,2);
    m := strtoint(ss);
    ss := Copy(s,7,2);
    d := strtoint(ss);
    date := EncodeDate(y,m,d);
    r := 0;            //date ok
  except
    on EConvertError do
      r := -1;         //date not ok
  end;

  if r = 0 then begin //date ok
    try
      ss := copy(s,9,10);
      v  := strtofloat(ss);
    except
      on EConvertError do begin
        v := -99.9;  //missing value;
        r := 1;
      end;
    end;
  end;

  Result := r;
  
end;

{----------------------------------------------------------------------------}

procedure Write_Header(var f : textfile) ;

  var
    l : integer ;

  begin
    for l := 1 to 58 do write(f,'-') ; writeln(f) ;
    writeln(f, 'Description   : ') ;
    writeln(f, 'Units         : m3/s' ) ;
    writeln(f, 'Origin        : DWA Website') ;
    for l := 5 to 9 do writeln(f,'-') ;
    writeln(f, 'Run Date      : ', DateTimeToStr(Now) ) ;
    for l := 1 to 58 do write(f,'-') ; writeln(f) ;
    writeln(f) ;
  end ;

{----------------------------------------------------------------------------}

procedure Write_Data(var f : textfile; data : Daily_Type) ;

  var
    tot    : real;
    DIM, D : integer ;
    nd     : integer ;

  begin
    DIM := DaysInMonth( EncodeDate(data.year, data.month, 1) ) ;
    tot := 0 ;
    for d := 1 to DIM do if (data.v[d] >= 0) then tot := tot + data.v[d];

    writeln(f, data.year:2, data.month:3, (tot*24*3600*1e-6):11:3);    {m3/s->M.m3}
    for d := 1 to DIM do begin
      if (data.v[d] >= 100.0) OR (data.v[d] < -99) then nd := 2
                                                   else nd := 3 ;
      write(f, data.v[d]:7:nd) ;                                    {m3/s}
      if ((d mod 7) = 0) OR (d=DIM) then writeln(f) ;
    end ;
    if ( DIM = 28 ) then writeln(f) ;
  end ;

  {----------------------------------------------------------------------------}

procedure ReadMonthlyData ;

  var
    m : byte ;
  begin
    with d do begin
      read  ( f, year ) ;
      if year < 1900 then year := year +1900;          {check whether works for all files}
      for m := 1 to 12 do read( f, v[m] ) ;
      readln( f ) ;
    end ;
  end ;

procedure ReadDailyData ;

  var
    dd, dim : byte ;
    code    : integer ;
    s7      : string[7] ;
  begin
    with d do begin
      read( f, year, month ) ;
      {if (year > 1900) then dec(year,1900) ;}
      if year < 1900 then year := year +1900;          {check whether works for all files}
      if EOLn(f) then total := -99.99 else read( f, total ) ;
      readln( f ) ;
      DIM := DaysInMonth( EncodeDate(year, month, 1) ) ;
      for dd := 1 to dim do begin
        read(f, s7 ) ; val(s7, v[dd], code ) ;
        if ( (dd=7)  or (dd=14) or
             (dd=21) or (dd=28) or (dd=dim) ) then readln( f ) ;
      end ;
      if ( dim = 28 ) then readln(f) ;
    end ;
  end ;


procedure ReadHourlyData ;

  var
    h : byte ;
  begin
    with d do begin
      readln( f, year, month, day ) ;
      if year < 1900 then year := year +1900;          {check whether works for all files}
      for h := 1 to 24 do begin
        read( f, v[h] ) ;
        if ( (h=8) or (h=16) or (h=24) ) then readln( f ) ;
      end ;
    end ;
  end ;


procedure ReadMin6Data ;

  var
    h, m : byte ;
  begin
    with d do begin
      readln( f, year, month, day ) ;
      for h := 1 to 24 do for m := 1 to 10 do read( f, v[h,m] ) ;
      readln( f ) ;
    end ;
  end ;


procedure ZeroMonthlyData ;

  var
    m : byte ;
  begin
    d.year := 0 ;
    for m := 1 to 12 do d.v[m] := 0 ;
  end ;


procedure ZeroDailyData ;

  var
    dd : byte ;
  begin
    d.year := 0 ;  d.month := 0 ;
    for dd := 1 to 31 do d.v[dd] := -99.9 ;
  end ;


procedure ZeroHourlyData ;

  var
    h : byte ;
  begin
    d.year := 0 ;  d.month := 0 ;  d.day := 0 ;
    for h := 1 to 24 do d.v[h] := 0 ;
  end ;


procedure ZeroMin6Data ;

  var
    h, m : byte ;
  begin
    d.year := 0 ;  d.month := 0 ;  d.day := 0 ;
    for h := 1 to 24 do for m := 1 to 10 do d.v[h,m] := 0 ;
  end ;


procedure SetFileToStart ;

  var
    i, off   : integer ;
    y, mm, d : longint ;
    vm       : Monthly_Type ;
    vd       : Daily_Type ;
    vh       : Hourly_Type ;
    v6       : Min6_Type ;

  begin
    if (sy < 1900) then inc(sy,1900) ;
    off := 0 ;
    for i := 1 to nhl do readln( f ) ;
    repeat
      inc( off ) ;
      case t of
        'M' : begin
                ReadMonthlyData ( f, vm ) ;
                y := vm.year ; mm := sm       ; d := 1 ;
              end ;
        'D' : begin
                ReadDailyData ( f, vd ) ;
                y := vd.year ; mm := vd.month ; d := 1 ;
              end ;
        'H' : begin
                ReadHourlyData ( f, vh ) ;
                y := vh.year ; mm := vh.month ; d := vh.day ;
              end ;
        '6' : begin
                ReadMin6Data ( f, v6 ) ;
                y := v6.year ; mm := v6.month ; d := v6.day ;
              end ;
      end ;
      if (y < 1900) then inc(y,1900) ;
      if (off = 1) AND
         ( (y*10000+mm*100+d) > (sy*10000+sm*100+1) ) then begin
         ShowMessage(' Error ! File '+s+' starts after Start Date ' ) ;
         Halt ;
      end ;
      if EOF( f ) then begin
        ShowMessage(' Error ! File '+s+' ends before Start Date ' ) ;
        Halt ;
      end ;
    until (d = 1) and (mm = sm) and (y = sy) ;
    reset( f ) ;
    for i := 1 to nhl do readln( f ) ;
    for i := 1 to (off-1) do begin
      case t of
        'M' : ReadMonthlyData( f, vm ) ;
        'D' : ReadDailyData  ( f, vd ) ;
        'H' : ReadHourlyData ( f, vh ) ;
        '6' : ReadMin6Data   ( f, v6 ) ;
      end ;
    end ;
  end ;


procedure GetFileStartDate ;

  var
    i, off   : integer ;
    d        : longint ;
    vm       : Monthly_Type ;
    vd       : Daily_Type ;
    vh       : Hourly_Type ;
    v6       : Min6_Type ;

  begin
    for i := 1 to nhl do readln( f ) ;
    case t of
      'M' : begin
              ReadMonthlyData ( f, vm ) ;
              sy := vm.year ; sm := sm       ;
            end ;
      'D' : begin
              ReadDailyData ( f, vd ) ;
              sy := vd.year ; sm := vd.month ;
            end ;
      'H' : repeat
              ReadHourlyData ( f, vh ) ;
              sy := vh.year ; sm := vh.month ; d := vh.day ;
            until EOF(f) or (d = 1) ;
      '6' : begin
              ReadMin6Data ( f, v6 ) ;
              sy := v6.year ; sm := v6.month ; d := v6.day ;
            end ;
    end ;
    if EOF( f ) then begin
      ShowMessage(' Error ! File ends before data found' ) ;
      Halt ;
    end ;
    reset(f) ;
  end ;

{-----------------------------------------------------------------------------}

procedure WriteDailyData ;

  var
    dd, DIM, dec : integer ;

  begin
    with d do begin
      DIM   := DaysInMonth( EncodeDate(year, month, 1) ) ;
      total := 0 ;
      for dd := 1 to DIM do
        total := total + v[dd] ;
      total := total /1e6*3600*24 ;        (* cum m3/s --> Mm3/month *)
      if (total < 0) then total := -99.99 ;

      writeln(f, year:3, month:3, total:10:3 ) ;
      for dd := 1 to DIM do begin
        dec := 3 ;
        if (v[dd] < 0) then dec := 2 ;
        if (v[dd] > 99) then dec := 2 ;
        if (v[dd] >999) then dec := 1 ;
        write(f, v[dd]:7:dec ) ;
        if ( (dd mod 7) = 0 ) then writeln(f) ;
      end ;
      writeln(f) ;
    end ;
  end ;

{-----------------------------------------------------------------------------}

procedure WriteHourlyData ;

  var
    h, dec : integer ;
    total : real ;

  begin
    with d do begin
      total := 0 ;
      for h := 1 to 24 do
        total := total + v[h] ;
      total := total /24 ;        (* cum m3/s --> m3/s *)
      if (total < 0) then total := -99.99 ;

      writeln(f, year:2, month:3, day:3, total:10:4 ) ;
      for h := 1 to 24 do begin
        dec := 4 ;
        write(f, v[h]:10:dec ) ;
        if ( (h mod 8) = 0 ) then writeln(f) ;
      end ;
    end ;
  end ;

{----------------------------------------------------------------------------}
begin
end.
{----------------------------------------------------------------------------}
