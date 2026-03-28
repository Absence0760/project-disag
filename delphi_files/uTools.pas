{----------------------------------------------------------------------------}
{  U n i t    : T O O L S                                                    }
{----------------------------------------------------------------------------}
{ Description :                                                              }
{                                                                            }
{ Written by  : AJ Greyling ................................... ... 88 [1.0] }
{ Modified by : AJ Greyling ................................ .. ... ..       }
{               - Modify/add trim routines, uppercase           ... ..       }
{               - Add exceedance routines                       Jul 94       }
{                                                                            }
{ Notes : - Usage of exceedance procedures :                                 }
{             requirements for calling program,                              }
{                                                                            }
{               var ExcNoInts              : integer ;                       }
{                   X, Y                   : array[1..MaxPoints] of real ;   }
{                   ExcMin, ExcMax         : real ;                          }
{                   ExcNoAbove, ExcNoBelow : integer ;                       }
{                                                                            }
{----------------------------------------------------------------------------}
unit uTools ;

INTERFACE

{uses  Dos ;}
uses SysUtils;

{----------------------------------------------------------------------------}
type
  rArray  = array[1..10600] of real ;    p_rArray = ^rArray ;
  iArray  = array[1..10600] of integer ; p_iArray = ^iArray ;
(*pArray  = array[1..10600] of pointer ; p_pArray = ^pArray ;*)
  rArray0 = array[0..10600] of real ;    p_rArray0 = ^rArray0;

  p_real    = ^real ;
  p_integer = ^integer ;

  realpointtype = record
                    x, y : real ;
                  end ;

  pArray = array[1..5300] of realpointtype ; p_realpointarraytype = ^pArray ;

{--- data types }
type
  Tanndata = array[1..12,1..32] of real ;
  Panndata = ^Tanndata ;

  Tdate = record
            yr, mt, dy : longint ;
          end ;

{----------------------------------------------------------------------------}

{--- global size for all path names, DataPath }
const
  DP_size = 50 ;
type
  strDP_size = string[DP_size] ;

{--- keys }
const
  NUL  = #00;  SPACE= #32;  BS   = #08;  BEL  = #07;
  LF   = #10;  CR   = #13;  ESC  = #27;  SP   = #32;
  FF   = #12;
  UP   = #72;  DOWN = #80;  LEFT = #75;  RIGHT= #77;
  HOME = #71;  BOT  = #79;  INS  = #82;  DEL  = #83;
  PgUp = #73;  PgDn = #81;  F1   = #59;  F2   = #60;
  F3   = #61;  F4   = #62;  F5   = #63;  F6   = #64;
  F7   = #65;  F8   = #66;  F9   = #67;  F10  = #68;
  ON   =true;  OFF  = false ;
  NL   = #13#10 ;
  TOP  = #71;

  ArrowKeys = UP+DOWN+LEFT+RIGHT ;

{--- strings }
type
  Str3  = string[ 3] ;    Str4  = string[ 4] ;
  Str6  = string[ 6] ;    Str8  = string[ 8] ;
  Str10 = string[10] ;    Str40 = string[40] ;
  Str12 = string[12] ;    Str45 = string[45] ;
  Str15 = string[15] ;    Str50 = string[50] ;
  Str20 = string[20] ;    Str60 = string[60] ;
  Str25 = string[25] ;    Str65 = string[65] ;
  Str30 = string[30] ;    Str70 = string[70] ;
  Str35 = string[35] ;    Str80 = string[80] ;

{--- toggle for unit screens }
type
  Toggle_Str = string[10];

{--- OnOff }
type   OnOff_Type = (  OnOff_Off, OnOff_On ) ;
const  OnOff_Values : array[0..1] of OnOff_Type =
                    (  OnOff_Off, OnOff_On ) ;
       OnOff_Select : array[0..1] of Toggle_Str =
                    ( 'Off',' On') ;

{--- YesNo }
type   YesNo_Type = (  YesNo_No, YesNo_Yes ) ;
const  YesNo_Values : array[0..1] of YesNo_Type =
                    (  YesNo_No, YesNo_Yes ) ;
       YesNo_Select : array[0..1] of Toggle_Str =
                    ( ' No','Yes') ;

{--- range line/symbols }
type  TMonTxt      = (_m,_Jan,_Feb,_Mar,_Apr,_May,_Jun,_Jul,_Aug,_Sep,_Oct,_Nov,_Dec);
const  MonTxt_No   = 12 ;
       MonTxt_Values : array[0..MonTxt_No] of TMonTxt =
                     (_m,_Jan,_Feb,_Mar,_Apr,_May,_Jun,_Jul,_Aug,_Sep,_Oct,_Nov,_Dec);
       MonTxt_Select : array[0..MonTxt_No] of Toggle_Str =
                     ('m','Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec');

{--- month strings }
const
  MonthStr : array[0..13] of str3 =
  ('','Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec','' );
  HydroMonthStr : array[0..13] of str3 =
  ('','Oct','Nov','Dec','Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','' );
  dash80 : string[80] = '--------------------------------------------------'+
                        '------------------------------' ;
{--- version }
var
  VersionStr : str20 ;
type
  TCFGversionStr = str15 ;

{--- screen mode graphics or text }
var
  ScreenModeGraphics : boolean ;

{----------------------------------------------------------------------------}

function  TrimChar        ( s : string; ch : char ):string;
function  TrimBlanks      ( s : string ): string;
function  TrimBlanksZeros ( s : string ): string;
function  Blanks2zeros    ( s : string ): string;
function  UpperCase       ( s : string ): string;
function  RightPadStr     ( s : string; c : char; n : byte ):string ;
function  Ljust           ( s : string; n : integer ): string ;
function  Rjust           ( s : string; n : integer ): string ;
function  Cjust           ( s : string; n : integer ): string ;
function  strf            ( v : real; l,d : byte    ): string ;
function  npos            ( c : char; s: string     ): integer;

function  IsIn            ( ch:char ; s:string) : boolean ;

function  GetFromFunction ( v:real; n:integer; Xp, Yp:pointer ):real ;
function  GetStepFunction ( v:real; n:integer; Xp, Yp:pointer ):real ;
function  GetSimpsons     ( Xp:pointer; d:real; n:integer     ):real ;
function  GetArrayMax     ( Xp:pointer;         n:integer     ):real ;
function  GetMax          ( a,b:real                          ):real ;

function  DaysInMonth     ( y, m        : integer ) : integer ;
function  DaysInHydroMonth( hy, hm      : integer ) : integer ;
function  GetDateTimeString                         : string ;
function  GetFileDateTimeString( var f ): string ;
function  GetNoDays       ( sd, ed      : longint ) : integer ;
procedure IncDate         ( var y, m, d : longint ) ;
procedure DecDate         ( var y, m, d : longint ) ;
procedure IncMonth        ( var y, m    : longint ) ;
procedure DecMonth        ( var y, m    : longint ) ;
procedure date2ymd        (     date    : longint ;
                            var y, m, d : longint ) ;
function  SetDateTimeStr  ( y,m,d,h,l: integer): string;
function  ymd2date        (     y, m, d : longint ) : longint ;
function  SetPeriodStrYM  ( sy,sm,ey,em : integer ) : string ;
function  MonthStr2no     ( s : string )            : integer ;
procedure Inc_YearMonth   ( var y,m,n   :integer  ) ;
function  JulianDay       ( var y,m,d   : integer ) : integer ;
procedure JulianDay2ymd   ( jd : longint; var y,m,d : integer ) ;
function  IncJulianDay    (     jd, n   : longint ) : longint ;
function  DecJulianDay    (     jd, n   : longint ) : longint ;
function  GapJulianDay    (     jd1, jd2: longint ) : longint ;

function  DatesEqual      ( date1, date2 : Tdate ) : boolean ;


procedure SortReal        ( p           : p_iArray;
                            Lo, Hi      : integer;
                            a           : p_rArray ) ;
procedure SortRealAndSwap ( Lo, Hi      : integer;
                            a           : p_rArray ) ;
function  Find_Closest_Point( x, y       : p_rArray;
                             n          : word;
                             px,py,tol  : real ) : word ;
function  Pwr             ( x, y : real ) : real ;
function  Log10           ( x    : real ) : real;
function  Pwr10           ( y    : real ) : real;

function  Min0            ( a,b : real ) : real ;
function  Min             ( a,b : real ) : real ;
function  Max             ( a,b : real ) : real ;
procedure Add             ( var a : real ; b : real ) ;
procedure Sub             ( var a : real ; b : real ) ;

procedure Dash            ( var f : text ; n : byte ; c : char ) ;
procedure SetVersionStr   ( v : real ) ;
procedure ReadCFGversion  ( var f : file ; var v : real ) ;
procedure WriteCFGversion ( var f : file ; v : real ) ;

function  Check_Parameters ( s : string ) : boolean ;

function  Calc_Mode        ( v : p_rArray; NoVals:integer;
                              min, max:real; NoInts:integer ) : real ;

procedure FileSplit        ( s : string; var path:strDP_size;
                                         var name:str8;
                                         var ext:str3 ) ;

function  OnOff_2_Boolean  ( onoff : OnOff_Type ): boolean ;
function  Boolean_2_OnOff  ( onoff : boolean    ): OnOff_Type ;
function  YesNo_2_Boolean  ( YesNo : YesNo_Type ): boolean ;
function  Boolean_2_YesNo  ( YesNo : boolean    ): YesNo_Type ;
function  bool2int         ( b:boolean          ): integer ;
function  int2bool         ( i: integer         ): boolean ;


{----- exceedance curves }

procedure exc_Initialise ( min, max : real ;
                           noints   : integer ;
                           X, Y     : p_rArray ;
                           noabove,
                           nobelow  : p_integer ) ;

procedure exc_ProcessValue ( v      : real ) ;

procedure exc_CalcResult ;

{----------------------------------------------------------------------------}
 IMPLEMENTATION
{----------------------------------------------------------------------------}

{----- exceedance curve variables }
var
  exc_inc, exc_min      : real ;
  exc_X, exc_Y          : p_rArray ;
  exc_noints, exc_total : integer ;
  exc_above, exc_below  : p_integer ;

{--------------------------------------------------------------------------}

procedure exc_Initialise ;

  var
    i : integer ;

  begin
    exc_inc := (max - min) / noints ;
    exc_noints := noints ;
    exc_X := X ;
    exc_Y := Y ;
    exc_total := 0 ;
    exc_above := noabove ; exc_above^ := 0 ;
    exc_below := nobelow ; exc_below^ := 0 ;
    for i := 1 to exc_noints do begin
      exc_X^[i] := 0 ;
      exc_Y^[i] := 0 ;
    end ;
  end ;

{--------------------------------------------------------------------------}

procedure exc_ProcessValue ;

  var
    i : integer ;

  begin
    i := trunc((v - exc_min) / exc_inc)+1 ;
    if (i < 1)          then inc(exc_below^) else
    if (i > exc_noints) then inc(exc_above^) else
                             exc_X^[i] := exc_X^[i] + 1 ;
    inc(exc_total) ;
  end ;

{--------------------------------------------------------------------------}

procedure exc_CalcResult ;

  var
    i   : integer ;
    sum : real ;

  begin
    sum := exc_above^ ;
    for i := exc_noints downto 1 do begin
      sum := sum + exc_X^[i] ;
      exc_X^[i] := sum / exc_total * 100 ;
      exc_Y^[i] := (i-1) * exc_inc + exc_min ;
    end ;
  end ;

{----------------------------------------------------------------------------}

function Ljust ;

  var
    p : integer ;
  begin
    for p := 1 to (n-length(s)) do s := s+' ' ;  Ljust := s ;
  end ;

{----------------------------------------------------------------------------}

function Rjust ;

  var
    p : integer ;
  begin
    for p := 1 to (n-length(s)) do s := ' '+s ;  Rjust := s ;
  end ;

{----------------------------------------------------------------------------}

function Cjust ;

  var
    p, l : integer ;
  begin
    l := ((n-length(s)) div 2) ;
    for p := 1 to l do s := ' '+s ;
    l := n-length(s)-l ;
    for p := 1 to l do s := s+' ' ;  Cjust := s ;
  end ;

{----------------------------------------------------------------------------}

function  strf ;

    var
      s : string ;
    begin
      str(v:l:d,s) ;  strf := s ;
    end ;

{----------------------------------------------------------------------------}

function  npos ;

    var
      i : integer;
    begin
      c := UpCase(c);
      i := 1;
      while i <= length(s) do if (UpCase(s[i]) = c) then inc(i);
      if i <= length(s) then npos := i
                        else npos := 0;
    end ;

{----------------------------------------------------------------------------}

function TrimChar;
  var
    b, e, l : integer;
  begin
    l := length(s);
    if l > 0 then begin
      b:=0; e:=l+1;
      repeat inc(b); until (s[b]<>ch) or (b>=l);
      repeat dec(e); until (s[e]<>ch) or (e<=1);
      l:=e-b+1;
    end;
    if l>0 then TrimChar := copy( s, b, l )
           else TrimChar := '';
    if (length(s)=1) and (s[1]=ch) then TrimChar := '';
  end;  {func}

{----------------------------------------------------------------------------}

function TrimBlanks;
  begin
    TrimBlanks := TrimChar( s, ' ');
  end;

{----------------------------------------------------------------------------}

function TrimBlanksZeros;
  begin
    s := TrimChar( s, ' ' );
    if pos( '.', s ) > 0 then s := TrimChar( s, '0' );
    if s[1] = '.' then s := '0' + s;
    if s[length(s)] = '.' then s := s + '0';
    TrimBlanksZeros := s;
  end;

{----------------------------------------------------------------------------}

function Blanks2zeros;
  var
    p : byte;
  begin
    repeat
      p := pos(' ',s);
      if p > 0 then s[p] := '0';
    until p = 0;
    Blanks2zeros := s ;
  end;

{----------------------------------------------------------------------------}

function UpperCase;
  var
    i : byte;
  begin
    for i := 1 to length(s) do s[i] := UpCase( s[i] );
    UpperCase := s;
  end;

{----------------------------------------------------------------------------}

function RightPadStr;
  var
    i : byte;
  begin
    for i := length(s)+1 to n do s := s+c ;
    RightPadStr := s;
  end;

{----------------------------------------------------------------------------}

function IsIn ;
  var
    t:integer ;
  begin
    IsIn :=FALSE ;
    for t := 1 to Length(s) do if s[t]=ch then IsIn :=TRUE ;
  end ;

{----------------------------------------------------------------------------}

function GetFromFunction ;
  var
    f, m : real ;
    X, Y : p_rArray ;
    i    : integer ;
  begin
    X := Xp ;
    Y := Yp ;
    if v <= X^[1] then
      f := Y^[1]
    else
      if v >= X^[n] then
        f := Y^[n]
    else begin
      i := 0 ;
      repeat inc( i ) until X^[i] > v ;
      m := ( Y^[i]-Y^[i-1] ) / ( X^[i]-X^[i-1] ) ;
      f := Y^[i-1] + m*( v-X^[i-1] ) ;
    end ;
    GetFromFunction := f ;
  end ;

{----------------------------------------------------------------------------}

function GetStepFunction ;
  var
    f    : real ;
    X, Y : p_rArray ;
    i    : integer ;
  begin
    X := Xp ;
    Y := Yp ;
    if v <= X^[1] then
      f := Y^[1]
    else
      if v >= X^[n] then
        f := Y^[n]
    else begin
      i := 0 ;
      repeat inc( i ) until X^[i] > v ;
      f := Y^[i-1] ;
    end ;
    GetStepFunction := f ;
  end ;

{----------------------------------------------------------------------------}

function  GetSimpsons ;
  var
    X : p_rArray ;
    i : integer ;
    sum : real ;
  begin
    X := Xp ;
    sum := (X^[1]+X^[n])/2 ;
    for i := 2 to (n-1) do sum := sum + X^[i] ;
    GetSimpsons := d * sum ;
  end ;

{----------------------------------------------------------------------------}

function GetArrayMax ;
  var
    X   : p_rArray ;
    max : real ;
    i   : integer ;
  begin
    X := Xp ;
    max := -1e9 ;
    for i := 1 to n do
      if (X^[i] > max) then max := X^[i] ;
    GetArrayMax := max ;
  end ;

{----------------------------------------------------------------------------}

function GetMax ;
  begin
    if (a > b) then GetMax := a else GetMax := b ;
  end ;

{----------------------------------------------------------------------------}

function DaysInMonth ;
  begin
    case m of
      2 : if (y mod 4) = 0    then DaysInMonth := 29
                              else DaysInMonth := 28;
      1, 3, 5, 7, 8, 10, 12 :      DaysInMonth := 31;
      4, 6, 9, 11           :      DaysInMonth := 30;
    end;
  end;

{----------------------------------------------------------------------------}

function DaysInHydroMonth ;
  begin
    if (hm <= 3) then DaysInHydroMonth := DaysInMonth( hy,   hm+9 )
                 else DaysInHydroMonth := DaysInMonth( hy+1, hm-3 ) ;
  end ;

{----------------------------------------------------------------------------}

function GetDateTimeString ;
  begin
    //HB - wrapper for backward compatibility
    GetDateTimeString := DateTimeToStr(Now);
  end ;

{----------------------------------------------------------------------------}

function SetDateTimeStr( y,m,d,h,l: integer): string;
  var
    s : string;
    t : string[5];

  begin
    {y,m} if (y < 1900) then inc(y,1900); str(y,s); s := s+'-'+MonthStr[m]+'-';
    {d} str(d:2,t); if (t[1] = ' ') then t[1] := '0'; s := s+t+', ';
    {h} str(h:2,t); if (t[1] = ' ') then t[1] := '0'; s := s+t+':';
    {m} str(l:2,t); if (t[1] = ' ') then t[1] := '0'; s := s+t;
    SetDateTimeStr := s;
  end;

{----------------------------------------------------------------------------}

function GetFileDateTimeString ;
  begin
    //HB - wrapper for backward compatibility
    GetFileDateTimeString := 'Not implemented!';
  end ;

{----------------------------------------------------------------------------}

function  GetNoDays ;

  var
    y, m, d, ym, ym2, d2 : longint ;
    n : integer ;
  begin
    y := sd div 10000 ;
    m := (sd div 100) - y*100 ;
    d := sd - y*10000 - m*100 ;
    ym2:= ed div 100 ;
    d2 := ed - ym2*100 ;

    n := -(d-1) ;
    dec(m) ;
    repeat
      inc(m); if (m>12) then begin m := 1; inc(y); end;
      ym := y*100 + m ;
      n := n + DaysInMonth(y,m) ;
    until (ym >= ym2) ;
    n := n - DaysInMonth(y,m) + d2 ;
    GetNoDays := n ;
  end ;

{----------------------------------------------------------------------------}

procedure IncDate ;

  var
    nd : longint ;
  begin
    if (d < 28) then
      inc(d)
    else begin
      case m of
        1,3,5,7,8,10,12 : nd := 31 ;
        2 : if ((y mod 4) > 0) then nd := 28 else nd := 29 ;
      else
        nd := 30 ;
      end ;
      inc(d) ;
      if (d > nd) then begin
        d := 1 ;
        inc(m) ; if (m > 12) then begin m := 1 ; inc(y) ; end ;
      end ;
    end ;
  end ;

{----------------------------------------------------------------------------}

procedure DecDate ;

  begin
    dec(d) ;
    if (d < 1) then begin
      dec(m) ;
      if (m < 1) then begin
        m := 12 ;
        dec(y) ;
      end ;
      d := DaysInMonth(y,m) ;
    end ;
  end ;

{----------------------------------------------------------------------------}

procedure IncMonth ;

  begin
    inc(m) ;
    if (m > 12) then begin
      m := 1 ;
      inc(y) ;
    end ;
  end ;

procedure DecMonth ;

  begin
    dec(m) ;
    if (m < 1) then begin
      m := 12 ;
      dec(y) ;
    end ;
  end ;

{----------------------------------------------------------------------------}

procedure date2ymd ;

  begin
    y := date div 10000 ;
    m := date div 100 - y*100 ;
    d := date - y*10000 - m*100 ;
  end ;

{----------------------------------------------------------------------------}

function ymd2date ;

  begin
    ymd2date := y*10000 + m*100 + d ;
  end ;

{----------------------------------------------------------------------------}

function SetPeriodStrYM ;

  var
    s, t : string ;
  begin
    s := '';
    str(sy,t) ; s := s+t+'/';   if (sm < 10) then s := s+'0' ;
    str(sm,t) ; s := s+t+' - ';
    str(ey,t) ; s := s+t+'/';   if (em < 10) then s := s+'0' ;
    str(em,t) ; s := s+t ;
    SetPeriodStrYM := s ;
  end ;

{----------------------------------------------------------------------------}

function  MonthStr2no ;

  var
    s3   : str3 ;
    m, i : integer ;
  begin
    s3 := UpperCase(copy(s,1,3)) ;
    m := 0 ;
    i := 0 ;
    repeat
      inc(i) ;
      if (UpperCase(MonthStr[i]) = s3) then m := i ;
    until (m > 0) OR (i = 12) ;
    MonthStr2no := m ;
  end ;

{----------------------------------------------------------------------------}

procedure SortReal ;

  procedure srt ( l, r : integer ) ;
    var
      i, j, y : integer ;
      x       : real ;
    begin
      i := l ;  j := r ;  x := a^[ p^[ (l+r) div 2 ] ];
      repeat
        while a^[ p^[i] ] < x do inc (i) ;
        while a^[ p^[j] ] > x do dec (j) ;
        if i <= j then
        begin
          y := p^[i]; p^[i] := p^[j]; p^[j] := y ;
          inc(i) ; dec(j) ;
        end ;
      until i > j ;
      if l < j then srt ( l, j ) ;
      if i < r then srt ( i, r ) ;
    end ;  {proc}

  begin
    srt ( Lo, Hi ) ;
  end ; {proc}

{----------------------------------------------------------------------------}

procedure SortRealAndSwap ;

  procedure srt ( l, r : integer ) ;
    var
      i, j : integer ;
      x, y : real ;
    begin
      i := l ;  j := r ;  x := a^[ (l+r) div 2  ];
      repeat
        while a^[ i ] < x do inc (i) ;
        while a^[ j ] > x do dec (j) ;
        if i <= j then
        begin
          y := a^[i]; a^[i] := a^[j]; a^[j] := y ;
          inc(i) ; dec(j) ;
        end ;
      until i > j ;
      if l < j then srt ( l, j ) ;
      if i < r then srt ( i, r ) ;
    end ;  {proc}

  begin
    srt ( Lo, Hi ) ;
  end ; {proc}

{----------------------------------------------------------------------------}

  function Find_Closest_Point ;

    var
      ps, p : word ;
      ds, d : real ;
    begin
      ds := 1e9;  ps := 0 ;
      for p := 1 to n do begin
        d := sqrt( (px-x^[p])*(px-x^[p]) + (py-y^[p])*(py-y^[p]) ) ;
        if (d < ds) AND (d <= tol) then begin
          ds := d ;
          ps := p ;
        end ;
      end ;
      Find_Closest_Point := ps ;
    end ;

{----------------------------------------------------------------------------}

function Pwr ;
  begin
    if (x > 0) then Pwr := exp( y * ln(x) )
               else Pwr := 0;
  end;

function Pwr10 ;
  begin
    Pwr10 := exp( y * ln(10) ) ;
  end;

{----------------------------------------------------------------------------}

function Log10 ;
  begin
    Log10 := ln(x) / ln(10);
  end;

{----------------------------------------------------------------------------}

function Min0 ;
  begin
    if (b < a) then a := b;
    if (a < 0) then a := 0 ;
    Min0 := a ;
  end ;

function Min ;
  begin
    if (b < a) then a := b;
    Min := a ;
  end ;

function Max ;
  begin
    if (b > a) then a := b;
    Max := a ;
  end ;

procedure Add ;
  begin
    a := a + b ;
  end ;

procedure Sub ;
  begin
    a := a - b ;
  end ;

{----------------------------------------------------------------------------}

procedure Dash ;
  var
    i : byte ;
  begin
    for i := 1 to n do write( f, c ) ; writeln(f) ;
  end ;

{----------------------------------------------------------------------------}

procedure SetVersionStr ;

  var
    l : integer ;
  begin
    str( v:0:2, VersionStr ) ;
    l := length(VersionStr) ;
    if VersionStr[l] = '0' then VersionStr:= copy(VersionStr,1,l-1) ;
    VersionStr := '[ver '+TrimBlanks(VersionStr)+']' ;
  end ;

{----------------------------------------------------------------------------}

procedure ReadCFGversion ;

  var
    s : TCFGversionStr ;
    c : integer ;
  begin
    BlockRead(f, s, sizeof(TCFGversionStr) ) ;
    if (copy(s,1,8) = '[version') then
      val( copy(s,9,6), v, c )
    else begin
      v := 0.0 ;
      reset(f,1) ;
    end ;
  end ;

{----------------------------------------------------------------------------}

procedure WriteCFGversion ;

  var
    s : TCFGversionStr ;
    c : integer ;
  begin
    str(v:6:2, s) ;
    s := '[version'+s+']' ;
    BlockWrite(f, s, sizeof(TCFGversionStr) ) ;
  end ;

{----------------------------------------------------------------------------}

function  Check_Parameters ;

  var
    p : integer ;
  begin
    Check_Parameters := false ;
    for p := 1 to ParamCount do
      if (UpperCase(paramstr(p)) = UpperCase(s)) then
        Check_Parameters := true
  end ;

{----------------------------------------------------------------------------}

function  Calc_Mode ;
  var
    modes  : p_iArray ;
    n, idx : integer ;
    minc   : real ;

  begin
    GetMem( modes, NoInts*sizeof(integer) ) ;
      for n := 1 to NoInts do modes^[n] := 0 ;
      if (min > max) then begin
        minc := min ;
        min := max ;
        max := minc ;
      end ;
      minc := (max-min) / NoInts ;

      if (minc > 0) then begin
        for n := 1 to NoVals do begin
          if (v^[n] >= min) AND (v^[n] <= max) then begin
            idx := trunc( (v^[n]-min) / minc ) + 1 ;
            if (idx > NoInts) then idx := NoInts ;
            inc( modes^[idx] ) ;
          end ;
        end ;
        idx := 1 ;
        for n := 1 to NoInts do
          if (modes^[n] > modes^[idx]) then idx := n ;
        Calc_Mode := min+(idx-0.5)*minc ;
        end
      else
        Calc_Mode := 0 ;
    FreeMem( modes, NoInts*sizeof(integer) ) ;
  end ;

{----------------------------------------------------------------------------}

procedure Inc_YearMonth ;

  var
    i : integer ;
  begin
    for i := 1 to abs(n) do begin
      if (n >= 0) then begin
        inc(m) ;
        if (m > 12) then begin
          m := 1 ;
          inc(y) ;
        end ;
      end

      else begin
        dec(m) ;
        if (m < 1) then begin
          m := 12 ;
          dec(y) ;
        end ;
      end ;
    end
  end ;

{----------------------------------------------------------------------------}

function JulianDay ;

  var
    mm, n : integer ;
  begin
    mm := 1 ;
    n := 0 ;
    while (mm < m) do begin
      inc(n, DaysInMonth(y,mm)) ;
      inc(mm) ;
    end ;
    JulianDay := n + d ;
  end ;

{----------------------------------------------------------------------------}

procedure JulianDay2ymd ;

  var
    fin    : boolean ;
    DIM    : integer ;
    dd, yy : longint ;

  begin
    yy := jd div 1000 ;
    dd := jd - yy*1000 ;
    y  := yy ;
    d  := dd ;

    fin := false ;
    m := 1 ;
    repeat
       DIM := DaysInMonth(y,m) ;
      if (d > DIM) then begin
        dec(d,DIM) ;
        inc(m) ;
        end
      else
        fin := true ;
    until fin ;
  end ;

{----------------------------------------------------------------------------}

function IncJulianDay ;

  var
    y, d, JDIY, a : longint ;
  begin
    y := jd div 1000 ;
    d := jd - y*1000 ;
    repeat
      if ((y mod 4) = 0) then JDIY := 366 else JDIY := 365 ;
      a := JDIY-d ;
      if (a > n) then a := n ;
      inc(d,a) ;
      dec(n,a) ;
      if (n > 0) then begin
        inc(y) ;
        d := 0 ;
      end ;
    until (n = 0) ;
    IncJulianDay := y*1000 + d ;
  end ;

{----------------------------------------------------------------------------}

function DecJulianDay ;

  var
    y, d, JDIY, a : longint ;
  begin
    y := jd div 1000 ;
    d := jd - y*1000 ;
    repeat
      if ((y mod 4) = 0) then JDIY := 366 else JDIY := 365 ;
      a := d-1 ;
      if (a > n) then a := n ;
      dec(d,a) ;
      dec(n,a) ;
      if (n > 0) then begin
        dec(y) ;
        d := JDIY+1 ;
      end ;
    until (n = 0) ;
    DecJulianDay := y*1000 + d ;
  end ;

{----------------------------------------------------------------------------}

function GapJulianDay ;

  var
    jdt : longint ;

  var
    y1, d1, y2, d2, JDIY, n : longint ;
  begin
    if (jd1 > jd2) then begin
      jdt := jd1 ;
      jd1 := jd2 ;
      jd2 := jdt ;
    end ;

    y1 := jd1 div  1000 ;   y2 := jd2 div  1000 ;
    d1 := jd1 - y1*1000 ;   d2 := jd2 - y2*1000 ;
    n := 0 ;

    while (jd1 < jd2) do begin
      if (y1 <> y2) then begin
        if ((y1 mod 4) = 0) then JDIY := 366
                            else JDIY := 365 ;
        inc(n,JDIY-d1) ;
        inc(y1) ;
        d1 := 0 ;
      end
      else begin
        inc(n,d2-d1) ;
        d1 := d2 ;
      end ;
      jd1 := y1*1000+d1 ;
    end ;
    GapJulianDay := n ;
  end ;

{----------------------------------------------------------------------------}

function  DatesEqual ;

  begin
    if (date1.yr = date2.yr) AND
       (date1.mt = date2.mt) AND
       (date1.dy = date2.dy) then DatesEqual := true
                             else DatesEqual := false ;
  end ;

{----------------------------------------------------------------------------}

procedure FileSplit ;

  var
    p1, p2, l, i : integer ;
  begin
    p1 := 0 ; p2 := 0 ; l := length(s) ;
    for i := 1 to l do begin
      if (s[i] = ':') OR (s[i] = '\') then p1 := i ;
      if (s[i] = '.')                 then p2 := i ;
    end ;
    path := copy(s,1,p1) ;
    s    := copy(s,p1+1,l-p1) ;
    if (p2 = 0) then begin
      name := s ;
      ext  := '' ;
    end
    else begin
      p2 := p2-p1 ;
      name := copy(s,1,p2-1) ;
      ext  := copy(s,p2+1,length(s)-p2) ;
    end ;
    path := UpperCase(path) ;
    name := UpperCase(name) ;
    ext  := UpperCase(ext) ;
  end ;

{----------------------------------------------------------------------------}

function OnOff_2_Boolean ;

  begin
    if (onoff = OnOff_On) then OnOff_2_Boolean := true
                          else OnOff_2_Boolean := false ;
  end ;

function Boolean_2_OnOff ;

  begin
    if (onoff) then Boolean_2_OnOff := OnOff_On
               else Boolean_2_OnOff := OnOff_Off ;
  end ;

{----------------------------------------------------------------------------}

function YesNo_2_Boolean ;

  begin
    if (YesNo = YesNo_Yes) then YesNo_2_Boolean := true
                          else YesNo_2_Boolean := false ;
  end ;

function Boolean_2_YesNo ;

  begin
    if (YesNo) then Boolean_2_YesNo := YesNo_Yes
               else Boolean_2_YesNo := YesNo_No ;
  end ;

{----------------------------------------------------------------------------}

function  bool2int ;

  begin
    if b then bool2int := 1 else bool2int := 0 ;
  end ;

function  int2bool ;

  begin
    if (i > 0) then int2bool := true else int2bool := false ;
  end ;

  {----------------------------------------------------------------------------}
begin
  ScreenModeGraphics := false ;
end.
{----------------------------------------------------------------------------}
Notes :
