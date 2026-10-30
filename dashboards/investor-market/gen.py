import os,math
D=os.path.dirname(os.path.abspath(__file__))
CSS=open(os.path.join(D,'..','property-performance','index.html')).read().split('<style>')[1].split('</style>')[0]
CSS+="""
.r-3{grid-template-columns:1.35fr 1fr}.kpis5{grid-template-columns:repeat(5,1fr)}
.chips{display:flex;gap:6px;flex-wrap:wrap}.chip{border:1px solid var(--line);background:#fff;border-radius:20px;padding:5px 12px;font-size:12px;font-weight:600;color:var(--muted)}
.chip.on{background:var(--navy);color:#fff;border-color:var(--navy)}
.num{text-align:right;font-variant-numeric:tabular-nums}.tag{font-size:11px;font-weight:700;padding:2px 8px;border-radius:12px;background:var(--blue-soft);color:var(--blue)}
.bar{height:8px;border-radius:5px;background:var(--blue)}.st{display:flex;align-items:center;gap:8px;padding:7px 0;border-bottom:1px solid var(--grid);font-size:12.5px}
.dot{width:8px;height:8px;border-radius:50%}.foot2{color:var(--muted);font-size:11.5px;text-align:center;margin-top:18px}
@media(max-width:900px){.kpis5,.r-3,.r-2{grid-template-columns:1fr 1fr}}
"""
mk=[('Charlotte','NC',212400,318900,41,386),('Memphis','TN',118700,189500,38,512),('San Antonio','TX',176300,262100,52,1204),('Richmond','VA',208900,301400,33,298),('Fresno','CA',264500,378200,36,441),('Worcester','MA',287100,402600,29,187)]
mrow=''.join(f'<tr><td><b>{c}</b>, {s}</td><td class="num">${d:,}</td><td class="num">${so:,}</td><td class="num"><b>${so-d:,}</b> <span class="tag">{(so-d)/so*100:.0f}%</span></td><td class="num">{dom}</td><td class="num">{inv:,}</td></tr>' for c,s,d,so,dom,inv in sorted(mk,key=lambda r:r[2]-r[3]))
inv=[('Blue Ridge Home Buyers LLC',47,'Charlotte, Richmond'),('Lone Star Residential Fund II',41,'San Antonio'),('Bluff City Properties LLC',33,'Memphis'),('Valley Oak Holdings',26,'Fresno'),('Commonwealth Renovation Group',22,'Richmond, Worcester'),('Queen City Capital Partners',19,'Charlotte')]
irow=''.join(f'<tr><td class="num" style="color:var(--muted)">{i+1}</td><td><b>{n}</b><div class="sub">{m}</div></td><td style="width:34%"><div class="bar" style="width:{p/47*100:.0f}%"></div></td><td class="num"><b>{p}</b></td></tr>' for i,(n,p,m) in enumerate(inv))
fl=[('1418 Oakdale Ave','Memphis, TN','Nov 2025','$96,000','Aug 2026','$184,500','$88,500'),('7 Harwick Ct','Charlotte, NC','Jan 2026','$188,000','Sep 2026','$309,000','$121,000'),('2210 Grove Ave','Richmond, VA','Dec 2025','$151,500','Aug 2026','$248,000','$96,500'),('55 Laurel St','Worcester, MA','Feb 2026','$262,000','Sep 2026','$389,900','$127,900')]
frow=''.join(f'<tr><td><b>{a}</b><div class="sub">{c}</div></td><td>{b1}<div class="sub">{p1}</div></td><td>{b2}<div class="sub">{p2}</div></td><td class="num" style="color:var(--green)"><b>{g}</b></td></tr>' for a,c,b1,p1,b2,p2,g in fl)
# trend chart
ms=['Oct','Nov','Dec','Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep']
so=[291,289,286,284,287,292,297,302,306,307,305,309];di=[203,205,201,198,200,204,207,210,212,209,208,211]
W,H,L,T=560,380,40,14
def pts(a):return ' '.join(f'{L+i*(W-L-10)/11:.0f},{T+(320-v)/(320-180)*(H-T-24):.0f}' for i,v in enumerate(a))
grid=''.join(f'<line x1="{L}" x2="{W-10}" y1="{T+(320-v)/140*(H-T-24):.0f}" y2="{T+(320-v)/140*(H-T-24):.0f}" stroke="#eef2f7"/><text x="{L-6}" y="{T+(320-v)/140*(H-T-24)+4:.0f}" font-size="10" fill="#6b7a8d" text-anchor="end">${v}K</text>' for v in (190,230,270,310))
lab=''.join(f'<text x="{L+i*(W-L-10)/11:.0f}" y="{H-4}" font-size="10" fill="#6b7a8d" text-anchor="middle">{m}</text>' for i,m in enumerate(ms))
chart=f'<svg viewBox="0 0 {W} {H}" width="100%">{grid}<polygon points="{pts(so)} {pts(di[::-1]).replace(" "," ") if False else ""}" fill="none"/><polyline points="{pts(so)}" fill="none" stroke="#0f2846" stroke-width="2.5"/><polyline points="{pts(di)}" fill="none" stroke="#3b82f6" stroke-width="2.5" stroke-dasharray="6 4"/>{lab}</svg>'
ic=lambda p:f'<div class="kicon"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#2563eb" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{p}</svg></div>'
HOME='<path d="M3 11l9-7 9 7v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1z"/>';TAG='<path d="M20 12l-8 8-9-9V3h8z"/><circle cx="7.5" cy="7.5" r="1.5"/>';UP='<path d="M3 17l6-6 4 4 8-8"/><path d="M15 7h6v6"/>';CLK='<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>';BOX='<rect x="3" y="7" width="18" height="13" rx="1"/><path d="M8 7V4h8v3"/>'
def k(l,v,d,cls,p):return f'<div class="kpi"><div class="label">{l}{ic(p)}</div><div class="val">{v}</div><span class="delta {cls}">{d} <span class="vs">vs Aug</span></span></div>'
html=f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Investor Market Dashboard: Sample</title><style>{CSS}</style></head><body><div class="wrap">
<div class="top"><div class="brand"><div class="logo">{ic(HOME).replace('class="kicon"','').replace('#2563eb','#fff')}</div><div><h1>Investor Market Dashboard</h1><div class="sub">Harborline Capital Advisors &middot; client view</div></div></div>
<div><div class="chips"><span class="chip on">All markets</span><span class="chip">CA</span><span class="chip">MA</span><span class="chip">NC</span><span class="chip">TN</span><span class="chip">TX</span><span class="chip">VA</span></div><div class="period" style="margin-top:8px">Period <b>September 2026</b> &middot; refreshed Oct 1, 6:00 AM</div></div></div>
<div class="kpis kpis5">{k("Avg distressed price","$211,300","+1.6%","up",TAG)}{k("Avg sold price","$308,800","+1.4%","up",HOME)}{k("Gross spread","$97,500","+1.0%","up",UP)}{k("Avg days on market","38","+3 days","down",CLK)}{k("Active inventory","3,028","+4.1%","up",BOX)}</div>
<div class="row r-3"><div class="panel"><h2>Distressed vs sold price, 12 months</h2><p class="cap"><b style="color:var(--navy)">&#9644;</b> Avg sold &nbsp; <b style="color:#3b82f6">- -</b> Avg distressed (foreclosure, REO, short sale). The gap is the gross spread, before rehab costs.</p>{chart}</div>
<div class="panel"><h2>Top investor buyers this month</h2><p class="cap">Company buyers from recorded deeds, names grouped across LLC variations</p><table><tr><th>#</th><th>Company</th><th></th><th class="num">Buys</th></tr>{irow}</table></div></div>
<div class="panel" style="margin-bottom:16px"><h2>Markets ranked by gross spread</h2><p class="cap">City level, September 2026. Texas sold prices use listing data, since Texas does not publish sale prices.</p><table><tr><th>Market</th><th class="num">Avg distressed</th><th class="num">Avg sold</th><th class="num">Gross spread</th><th class="num">Days on market</th><th class="num">Inventory</th></tr>{mrow}</table></div>
<div class="row r-2"><div class="panel"><h2>Resold within 12 months</h2><p class="cap">Same property, two recorded sales inside 12 months</p><table><tr><th>Property</th><th>Bought</th><th>Resold</th><th class="num">Spread</th></tr>{frow}</table></div>
<div class="panel"><h2>Data refresh status</h2><p class="cap">Runs on its own each month. Checks stop bad data before it reaches the dashboard.</p>
{''.join(f'<div class="st"><span class="dot" style="background:{c}"></span><b style="width:150px">{a}</b><span style="color:var(--muted)">{b}</span></div>' for a,b,c in [("Deed records","48,212 rows, 6 states","#2e9e6b"),("Foreclosure feed","3,904 rows","#2e9e6b"),("Market listings","City level, all 6 states","#2e9e6b"),("Duplicate check","112 duplicates removed","#2e9e6b"),("Coverage check","2 counties late, flagged","#e0a133"),("Monthly email","Sent to 14 clients via GoHighLevel","#2e9e6b")])}
<p class="cap" style="margin-top:12px">Logins by role: Admin, Analyst, Client. Clients only see their own markets.</p></div></div>
<div class="foot2">Sample dashboard on demonstration data, built by William Lim. Company, property and investor names are fictional; figures illustrative.</div></div></body></html>'''
open(os.path.join(D,'index.html'),'w').write(html)
