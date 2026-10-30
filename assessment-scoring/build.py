from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.chart import RadarChart, Reference
from openpyxl.formatting.rule import CellIsRule, ColorScaleRule
from openpyxl.workbook.protection import WorkbookProtection

NAVY="1F3A5F"; INPUT="DCE9F7"; GREY="F3F4F6"
H=Font(bold=True,color="FFFFFF"); T=Font(bold=True,size=16,color=NAVY)
thin=Side(style="thin",color="D1D5DB"); B=Border(top=thin,bottom=thin,left=thin,right=thin)
def hdr(ws,row,vals):
    for i,v in enumerate(vals,1):
        c=ws.cell(row,i,v); c.font=H; c.fill=PatternFill("solid",fgColor=NAVY); c.alignment=Alignment(wrap_text=True,vertical="center"); c.border=B

wb=Workbook()
# ---------- Settings ----------
st=wb.active; st.title="Settings"
st["A1"]="Settings (locked)"; st["A1"].font=T
st["A2"]="Weights and maturity thresholds are set once per engagement. Answer scale: 1 (ad hoc) to 5 (optimized), or N/A."
hdr(st,4,["Dimension","Weight"])
dims=[("Process",0.30),("People",0.25),("Technology",0.25),("Measurement",0.20)]
for i,(d,w) in enumerate(dims,5):
    st.cell(i,1,d).border=B; c=st.cell(i,2,w); c.number_format="0%"; c.border=B
st["A9"]="Total"; st["B9"]="=SUM(B5:B8)"; st["B9"].number_format="0%"; st["A9"].font=Font(bold=True)
hdr(st,11,["Index from","Maturity level","Summary phrase"])
lv=[(0,"1 - Initial","is largely ad hoc and needs a basic framework"),(40,"2 - Developing","has foundations in place but applies them inconsistently"),(60,"3 - Defined","is documented and applied consistently"),(75,"4 - Managed","is measured and actively improved"),(90,"5 - Optimized","is a clear strength to build on")]
for i,(a,b,c) in enumerate(lv,12):
    for j,v in enumerate((a,b,c),1): st.cell(i,j,v).border=B
st.column_dimensions["A"].width=16; st.column_dimensions["B"].width=18; st.column_dimensions["C"].width=58

# ---------- Assessment ----------
a=wb.create_sheet("Assessment")
a["A1"]="Operations Department Assessment"; a["A1"].font=T
a["A2"]="Client:"; a["B2"]="Sample Co."; a["B2"].fill=PatternFill("solid",fgColor=INPUT)
a["D2"]="Blue cells are for input. Everything else is locked."
hdr(a,4,["#","Dimension","Question","Answer (1-5 or N/A)","Score used","Notes"])
qs=[("Process","Core workflows are documented and current.",4),
("Process","Hand-offs between teams follow a defined procedure.",3),
("Process","Exceptions are logged and reviewed.",2),
("People","Roles and responsibilities are clearly assigned.",4),
("People","Staff are trained on current procedures.",3),
("People","Backup coverage exists for key roles.","N/A"),
("Technology","Systems in use are fit for current volume.",3),
("Technology","Data is entered once and shared, not re-keyed.",2),
("Technology","Access and permissions are reviewed regularly.",4),
("Measurement","Department KPIs are defined and tracked.",2),
("Measurement","Results are reviewed with leadership monthly.",3),
("Measurement","Targets are set and compared with actuals.",1)]
dv=DataValidation(type="list",formula1='"1,2,3,4,5,N/A"',allow_blank=True,showErrorMessage=True,error="Choose 1 to 5 or N/A")
a.add_data_validation(dv)
for i,(d,q,v) in enumerate(qs,5):
    a.cell(i,1,i-4); a.cell(i,2,d); a.cell(i,3,q)
    c=a.cell(i,4,v); c.fill=PatternFill("solid",fgColor=INPUT); c.alignment=Alignment(horizontal="center"); dv.add(c)
    a.cell(i,5,f'=IF(ISNUMBER(D{i}),D{i},"")').alignment=Alignment(horizontal="center")
    n=a.cell(i,6); n.fill=PatternFill("solid",fgColor=INPUT)
    for j in range(1,7): a.cell(i,j).border=B
    a.cell(i,3).alignment=Alignment(wrap_text=True)
for col,w in zip("ABCDEF",(5,14,52,18,11,30)): a.column_dimensions[col].width=w
last=4+len(qs)

# ---------- Dashboard ----------
db=wb.create_sheet("Dashboard",0)
db["A1"]="Executive Dashboard"; db["A1"].font=T
db["A2"]='="Operations · "&Assessment!B2'
hdr(db,4,["Dimension","Avg answer (1-5)","Index (0-100)","Maturity level","Answered"])
for i,(d,_) in enumerate(dims,5):
    db.cell(i,1,d)
    db.cell(i,2,f'=IFERROR(AVERAGEIFS(Assessment!$E$5:$E${last},Assessment!$B$5:$B${last},A{i}),"")').number_format="0.0"
    db.cell(i,3,f'=IF(B{i}="","",ROUND((B{i}-1)/4*100,0))')
    db.cell(i,4,f'=IF(C{i}="","",VLOOKUP(C{i},Settings!$A$12:$B$16,2,TRUE))')
    db.cell(i,5,f'=COUNTIFS(Assessment!$B$5:$B${last},A{i},Assessment!$E$5:$E${last},">0")&" of "&COUNTIF(Assessment!$B$5:$B${last},A{i})')
    for j in range(1,6): db.cell(i,j).border=B
db["A10"]="Overall (weighted)"; db["A10"].font=Font(bold=True,size=12)
db["C10"]="=ROUND(SUMPRODUCT(C5:C8,Settings!B5:B8)/SUMPRODUCT((C5:C8<>\"\")*Settings!B5:B8),0)"
db["D10"]="=VLOOKUP(C10,Settings!$A$12:$B$16,2,TRUE)"
for c in ("C10","D10"): db[c].font=Font(bold=True,size=12,color=NAVY)
db.conditional_formatting.add("C5:C8",ColorScaleRule(start_type="num",start_value=0,start_color="F8696B",mid_type="num",mid_value=50,mid_color="FFEB84",end_type="num",end_value=100,end_color="63BE7B"))
db["A12"]="Executive summary"; db["A12"].font=Font(bold=True,size=12,color=NAVY)
db["A13"]=('="Overall, operations scores "&C10&" of 100 ("&D10&"). The strongest area is "&INDEX(A5:A8,MATCH(MAX(C5:C8),C5:C8,0))'
  '&", which "&VLOOKUP(MAX(C5:C8),Settings!$A$12:$C$16,3,TRUE)&". The priority is "&INDEX(A5:A8,MATCH(MIN(C5:C8),C5:C8,0))'
  '&", which "&VLOOKUP(MIN(C5:C8),Settings!$A$12:$C$16,3,TRUE)&"."')
db.merge_cells("A13:E19"); db["A13"].alignment=Alignment(wrap_text=True,vertical="top")
for col,w in zip("ABCDE",(20,17,14,18,11)): db.column_dimensions[col].width=w
ch=RadarChart(); ch.type="filled"; ch.style=26; ch.title="Maturity profile (0-100)"
ch.add_data(Reference(db,min_col=3,min_row=4,max_row=8),titles_from_data=True)
ch.set_categories(Reference(db,min_col=1,min_row=5,max_row=8))
ch.y_axis.scaling.min=0; ch.y_axis.scaling.max=100; ch.y_axis.majorUnit=25; ch.y_axis.delete=False
ch.legend=None; ch.height=8.5; ch.width=11
db.add_chart(ch,"A21")
for w in (db,a,st):
    w.page_setup.fitToWidth=1; w.page_setup.fitToHeight=0; w.sheet_properties.pageSetUpPr.fitToPage=True

# ---------- protection ----------
for ws in (st,db): ws.protection.sheet=True
a.protection.sheet=True
from openpyxl.styles import Protection
for i in range(5,last+1):
    for col in "DF": a[f"{col}{i}"].protection=Protection(locked=False)
a["B2"].protection=Protection(locked=False)
wb.security=WorkbookProtection(lockStructure=True)
wb.save("Assessment-Scoring-Sample-by-WilliamL.xlsx")
