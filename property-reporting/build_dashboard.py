#!/usr/bin/env python3
"""
Multifamily Property Performance Dashboard — Google Sheets-compatible sample.
Sample brief: automate GA4 + Google Business Profile + weekly Yardi
report into a Sheets database + management dashboard.

Design:
- Raw landing tabs (GA4, GBP, Yardi weekly — the Yardi tab is deliberately messy:
  title rows, a header NOT on row 1, a trailing TOTAL row, drifting property names).
- History = the append-only database (one row per property per week, composite key
  week_ending + property_id). The dashboard reads from History with SUMIFS/AVERAGEIFS
  so it is genuinely live.
- Dashboard = KPI cards + same-store property comparison + trend, all formula-driven.
- Review = where the automation routes anything it can't reconcile.
All formulas are Google-Sheets-safe (SUMIFS/AVERAGEIFS/IFERROR only).
"""
import datetime as dt
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.chart import LineChart, BarChart, Reference
from openpyxl.utils import get_column_letter

import os
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Property-Performance-Dashboard-SAMPLE-by-WilliamL.xlsx")

INK="1F2933"; NAVY="1E3A5F"; TEAL="0F766E"; TEAL_LT="CCE3E1"; SAND="FBF7EF"
GREY="F1F3F5"; YELLOW="FFF3BF"; LINE="D5DBDF"; AMBER="FCE0A8"; RED="F8B4A0"; GREEN="D8EFDC"

thin=Side(style="thin",color=LINE); border=Border(left=thin,right=thin,top=thin,bottom=thin)
def fill(h): return PatternFill("solid",fgColor=h)

# ------- mock portfolio -------
PROPS=[("P1","Maple Grove Apartments",320),
       ("P2","Riverside Commons",214),
       ("P3","Oak Park Residences",156)]
WEEKS=12
start=dt.date(2026,6,12)  # a Friday-ish weekly cadence
week_dates=[start+dt.timedelta(days=7*i) for i in range(WEEKS)]

# deterministic pseudo-values (no RNG so the file is reproducible / verifiable)
def val(seed, base, amp, drift=0.0, i=0):
    x=(seed*37+i*13)%100
    return round(base + amp*((x/100)-0.5)*2 + drift*i, 0)

# metric columns kept in History
HIST_COLS=["Week Ending","Property ID","Property","Units","Occupied","Leased",
           "Move-ins","Move-outs","Delinquencies","Applications",
           "Sessions","Users","Conversions","Leads",
           "GBP Calls","GBP Website Clicks","GBP Directions","GBP Views"]

def make_row(pid,pname,units,i):
    s=sum(ord(c) for c in pid)
    occ=min(units, max(int(units*0.9), int(units*0.90 + val(s,0,8,0.4,i))))
    leased=min(units, occ+int(val(s+1,4,4,0,i)))
    return [week_dates[i], pid, pname, units, occ, leased,
            int(val(s+2,6,4,0,i)), int(val(s+3,5,3,0,i)), int(val(s+4,3,3,-0.05,i)),
            int(val(s+5,14,8,0,i)), int(val(s+6,900,300,10,i)), int(val(s+7,640,200,8,i)),
            int(val(s+8,42,18,0.5,i)), int(val(s+9,55,20,0.6,i)),
            int(val(s+10,120,50,0,i)), int(val(s+11,240,90,3,i)),
            int(val(s+12,85,40,0,i)), int(val(s+13,3200,900,20,i))]

wb=Workbook()

# =====================================================================
# HISTORY (database)
# =====================================================================
h=wb.active; h.title="History"
h.sheet_properties.tabColor=NAVY
for c,t in enumerate(HIST_COLS,1):
    cell=h.cell(1,c,t); cell.font=Font(bold=True,color="FFFFFF"); cell.fill=fill(NAVY)
    cell.border=border; cell.alignment=Alignment(horizontal="center",vertical="center",wrap_text=True)
    h.column_dimensions[get_column_letter(c)].width=13 if c>3 else (14 if c==3 else 11)
h.column_dimensions["C"].width=24
h.freeze_panes="A2"
r=2
for i in range(WEEKS):
    for pid,pname,units in PROPS:
        row=make_row(pid,pname,units,i)
        for c,v in enumerate(row,1):
            cell=h.cell(r,c,v); cell.border=border; cell.font=Font(size=10,color=INK)
            if c==1: cell.number_format="yyyy-mm-dd"
        r+=1
LAST_HIST=r-1
h.cell(1,1).comment=None

# =====================================================================
# RAW: Yardi Weekly  (deliberately messy landing zone)
# =====================================================================
y=wb.create_sheet("Raw_Yardi_Weekly"); y.sheet_properties.tabColor="9AA5B1"
y.column_dimensions["A"].width=26
for i in range(2,10): y.column_dimensions[get_column_letter(i)].width=13
y.merge_cells("A1:H1")
t=y["A1"]; t.value="Yardi — Weekly Operations Report (Property Roll-Up)"
t.font=Font(bold=True,size=12,color=INK); t.fill=fill(SAND)
y["A2"]="Report generated"; y["B2"]=week_dates[-1].strftime("%m/%d/%Y")
y["A3"]="Week ending"; y["B3"]=week_dates[-1].strftime("%m/%d/%Y")
# header row is row 5 (NOT row 1) — parser must find it by name
yh=["Property","Units","Occupied","Leased","Move In","Move Out","Delinq.","Applications"]
for c,t in enumerate(yh,1):
    cell=y.cell(5,c,t); cell.font=Font(bold=True,color="FFFFFF"); cell.fill=fill("52616B")
    cell.border=border; cell.alignment=Alignment(horizontal="center")
# messy property names: trailing spaces, abbreviation drift
messy={"P1":"Maple Grove Apartments ","P2":"Riverside Commons","P3":"Oak Park Res."}
rr=6; tot=[0]*7
for pid,pname,units in PROPS:
    row=make_row(pid,pname,units,WEEKS-1)
    vals=[messy[pid],row[3],row[4],row[5],row[6],row[7],row[8],row[9]]
    for c,v in enumerate(vals,1):
        cell=y.cell(rr,c,v); cell.border=border; cell.font=Font(size=10)
    for k in range(7): tot[k]+=vals[k+1]
    rr+=1
# trailing TOTAL row that looks like data (parser must skip / use to reconcile)
cell=y.cell(rr,1,"TOTAL"); cell.font=Font(bold=True); cell.fill=fill(GREY); cell.border=border
for k in range(7):
    c=y.cell(rr,k+2,tot[k]); c.font=Font(bold=True); c.fill=fill(GREY); c.border=border
y.cell(rr+2,1,"Note: header is on row 5, names carry trailing spaces / abbreviations,")
y.cell(rr+3,1,"and the last row is a TOTAL subtotal. The Apps Script handles all three.")
for rn in (rr+2,rr+3): y.cell(rn,1).font=Font(size=9,italic=True,color="52616B")

# =====================================================================
# RAW: GA4 + GBP (stand-ins for the automated API pulls)
# =====================================================================
def simple_raw(title,color,cols,metric_idx):
    s=wb.create_sheet(title); s.sheet_properties.tabColor=color
    s.column_dimensions["A"].width=24
    for i in range(2,len(cols)+2): s.column_dimensions[get_column_letter(i)].width=15
    s.merge_cells(start_row=1,start_column=1,end_row=1,end_column=len(cols))
    tt=s.cell(1,1,title.replace("Raw_","Raw feed: ").replace("_"," ")+"  (auto-pulled)")
    tt.font=Font(bold=True,size=12,color=INK); tt.fill=fill(SAND)
    for c,t in enumerate(cols,1):
        cell=s.cell(3,c,t); cell.font=Font(bold=True,color="FFFFFF"); cell.fill=fill(TEAL)
        cell.border=border; cell.alignment=Alignment(horizontal="center")
    rr=4
    for pid,pname,units in PROPS:
        row=make_row(pid,pname,units,WEEKS-1)
        line=[pname]+[row[j] for j in metric_idx]
        for c,v in enumerate(line,1):
            cell=s.cell(rr,c,v); cell.border=border; cell.font=Font(size=10)
        rr+=1
    return s
simple_raw("Raw_GA4","BFD4E8",["Property","Sessions","Users","Conversions","Leads"],[10,11,12,13])
simple_raw("Raw_GBP","BFD4E8",["Property","Calls","Website Clicks","Directions","Views"],[14,15,16,17])

# =====================================================================
# REVIEW (exceptions the automation flags)
# =====================================================================
rv=wb.create_sheet("Review"); rv.sheet_properties.tabColor=AMBER
rv.column_dimensions["A"].width=16; rv.column_dimensions["B"].width=22
rv.column_dimensions["C"].width=20; rv.column_dimensions["D"].width=60
for c,t in enumerate(["Week Ending","Property","Check","Detail"],1):
    cell=rv.cell(1,c,t); cell.font=Font(bold=True,color="FFFFFF"); cell.fill=fill("B0752F"); cell.border=border
demo=[[week_dates[-1],"Oak Park Res.","name normalized","Matched 'Oak Park Res.' -> 'Oak Park Residences' via lookup"],
      [week_dates[-1],"(report total)","reconciliation OK","Sum of property rows == Yardi TOTAL row (units 690 = 690)"],
      [week_dates[-1],"Riverside Commons","anomaly flag","GBP direction-requests down 22% WoW — surfaced for review"]]
for i,row in enumerate(demo,2):
    for c,v in enumerate(row,1):
        cell=rv.cell(i,c,v); cell.border=border; cell.font=Font(size=10)
        if c==1: cell.number_format="yyyy-mm-dd"
    rv.cell(i,3).fill=fill(GREEN if "OK" in row[2] or "normalized" in row[2] else AMBER)

# =====================================================================
# DASHBOARD (formula-driven from History)
# =====================================================================
d=wb.create_sheet("Dashboard",0); d.sheet_properties.tabColor=TEAL
for col,w in {"A":3,"B":22,"C":14,"D":14,"E":14,"F":14,"G":14,"H":14,"I":14}.items():
    d.column_dimensions[col].width=w
HA="History!$A$2:$A$400"; HB="History!$B$2:$B$400"
def HC(letter): return f"History!${letter}$2:${letter}$400"

# title
d.merge_cells("B2:I2"); tt=d["B2"]; tt.value="Multifamily Property Performance"
tt.font=Font(bold=True,size=18,color=INK)
d.merge_cells("B3:I3"); st=d["B3"]
st.value="Live from the History database — GA4, Google Business Profile, and the weekly Yardi report, consolidated and refreshed on a schedule."
st.font=Font(size=10,italic=True,color="52616B")
d["B4"]="Latest week ending:"; d["B4"].font=Font(bold=True,size=10)
d["C4"]="=MAX(History!$A$2:$A$400)"; d["C4"].number_format="yyyy-mm-dd"; d["C4"].font=Font(bold=True,color=TEAL)
d["D4"]="=C4-7"; d["D4"].number_format="yyyy-mm-dd"  # prior week (weekly cadence)
d["E4"]="(prior week)"; d["E4"].font=Font(size=9,italic=True,color="9AA5B1")

LW="$C$4"; PW="$D$4"
def sumifs_latest(letter,wk=LW): return f"SUMIFS({HC(letter)},{HA},{wk})"

# KPI cards: (label, formula latest, formula prior for WoW, is_pct)
kpis=[
 ("Portfolio occupancy", f"=IFERROR(SUMIFS({HC('E')},{HA},{LW})/SUMIFS({HC('D')},{HA},{LW}),0)",
                          f"=IFERROR(SUMIFS({HC('E')},{HA},{PW})/SUMIFS({HC('D')},{HA},{PW}),0)", True),
 ("Leased %",            f"=IFERROR(SUMIFS({HC('F')},{HA},{LW})/SUMIFS({HC('D')},{HA},{LW}),0)",
                          f"=IFERROR(SUMIFS({HC('F')},{HA},{PW})/SUMIFS({HC('D')},{HA},{PW}),0)", True),
 ("Total leads",         f"=SUMIFS({HC('N')},{HA},{LW})", f"=SUMIFS({HC('N')},{HA},{PW})", False),
 ("Conversions",         f"=SUMIFS({HC('M')},{HA},{LW})", f"=SUMIFS({HC('M')},{HA},{PW})", False),
 ("GBP calls",           f"=SUMIFS({HC('O')},{HA},{LW})", f"=SUMIFS({HC('O')},{HA},{PW})", False),
 ("Website sessions",    f"=SUMIFS({HC('K')},{HA},{LW})", f"=SUMIFS({HC('K')},{HA},{PW})", False),
]
row0=6
for idx,(label,fl,fp,pct) in enumerate(kpis):
    col=2+(idx%3)*2  # B, D, F
    rr=row0+(idx//3)*4
    d.merge_cells(start_row=rr,start_column=col,end_row=rr,end_column=col+1)
    lc=d.cell(rr,col,label); lc.font=Font(bold=True,size=10,color=INK); lc.fill=fill(TEAL_LT); lc.border=border
    d.cell(rr,col+1).fill=fill(TEAL_LT); d.cell(rr,col+1).border=border
    vc=d.cell(rr+1,col,fl); vc.font=Font(bold=True,size=17,color=TEAL); vc.border=border
    vc.number_format=("0.0%" if pct else "#,##0")
    vc.alignment=Alignment(horizontal="left",indent=1)
    d.cell(rr+1,col+1).border=border; d.merge_cells(start_row=rr+1,start_column=col,end_row=rr+1,end_column=col+1)
    # WoW delta
    if pct:
        wow=f"=({fl[1:]})-({fp[1:]})"; fmt="+0.0%;-0.0%"
    else:
        wow=f"=IFERROR((({fl[1:]})-({fp[1:]}))/({fp[1:]}),0)"; fmt="+0.0%;-0.0%"
    wc=d.cell(rr+2,col,wow); wc.number_format=fmt; wc.font=Font(size=9,italic=True,color="52616B"); wc.border=border
    d.cell(rr+2,col+1,"WoW"); d.cell(rr+2,col+1).font=Font(size=9,italic=True,color="9AA5B1"); d.cell(rr+2,col+1).border=border

# ---- same-store property comparison ----
cmp_row=15
d.cell(cmp_row,2,"Same-store property comparison (latest week)").font=Font(bold=True,size=12,color=INK)
headers=["Property","Occupancy","Leased %","Move-ins","Move-outs","Delinq.","Leads","GBP calls"]
for c,htext in enumerate(headers):
    cell=d.cell(cmp_row+1,2+c,htext); cell.font=Font(bold=True,color="FFFFFF"); cell.fill=fill(NAVY)
    cell.border=border; cell.alignment=Alignment(horizontal="center")
metric_for={"Occupancy":("E","D"),"Leased %":("F","D"),"Move-ins":("G",None),"Move-outs":("H",None),
            "Delinq.":("I",None),"Leads":("N",None),"GBP calls":("O",None)}
for i,(pid,pname,units) in enumerate(PROPS):
    r=cmp_row+2+i
    nc=d.cell(r,2,pname); nc.border=border; nc.font=Font(size=10)
    for c,htext in enumerate(headers[1:]):
        num,den=metric_for[htext]
        if den:
            f=f"=IFERROR(SUMIFS({HC(num)},{HA},{LW},{HB},\"{pid}\")/SUMIFS({HC(den)},{HA},{LW},{HB},\"{pid}\"),0)"
            fmt="0.0%"
        else:
            f=f"=SUMIFS({HC(num)},{HA},{LW},{HB},\"{pid}\")"; fmt="#,##0"
        cell=d.cell(r,3+c,f); cell.number_format=fmt; cell.border=border; cell.font=Font(size=10)
        cell.alignment=Alignment(horizontal="center")

# ---- weekly trend helper table (portfolio occupancy % + total leads per week) ----
tr_row=cmp_row+7
d.cell(tr_row,2,"Portfolio trend (last 12 weeks)").font=Font(bold=True,size=12,color=INK)
d.cell(tr_row+1,2,"Week"); d.cell(tr_row+1,3,"Occupancy"); d.cell(tr_row+1,4,"Leads")
for c in (2,3,4): d.cell(tr_row+1,c).font=Font(bold=True,color="FFFFFF"); d.cell(tr_row+1,c).fill=fill(TEAL)
for i,wd in enumerate(week_dates):
    r=tr_row+2+i
    wc=d.cell(r,2,wd); wc.number_format="mm/dd"; wc.font=Font(size=9); wc.border=border
    oc=d.cell(r,3,f"=IFERROR(SUMIFS({HC('E')},{HA},$B{r})/SUMIFS({HC('D')},{HA},$B{r}),0)")
    oc.number_format="0.0%"; oc.font=Font(size=9); oc.border=border
    lc=d.cell(r,4,f"=SUMIFS({HC('N')},{HA},$B{r})"); lc.number_format="#,##0"; lc.font=Font(size=9); lc.border=border
TR_FIRST=tr_row+2; TR_LAST=tr_row+1+len(week_dates)

# charts
occ_chart=BarChart(); occ_chart.type="col"; occ_chart.title="Occupancy by property (latest week)"
occ_chart.height=7; occ_chart.width=12; occ_chart.legend=None
data=Reference(d,min_col=3,min_row=cmp_row+1,max_row=cmp_row+1+len(PROPS))
cats=Reference(d,min_col=2,min_row=cmp_row+2,max_row=cmp_row+1+len(PROPS))
occ_chart.add_data(data,titles_from_data=True); occ_chart.set_categories(cats)
d.add_chart(occ_chart,"F15")

trend=LineChart(); trend.title="Portfolio leads — weekly trend"; trend.height=7; trend.width=12; trend.legend=None
tdata=Reference(d,min_col=4,min_row=tr_row+1,max_row=TR_LAST)
tcats=Reference(d,min_col=2,min_row=TR_FIRST,max_row=TR_LAST)
trend.add_data(tdata,titles_from_data=True); trend.set_categories(tcats)
d.add_chart(trend,"F"+str(tr_row+1))

wb.save(OUT)
print("saved",OUT)

