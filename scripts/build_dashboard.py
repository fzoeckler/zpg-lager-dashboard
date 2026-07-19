#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ZPG Lager-Dashboard Generator.
Liest data.json und erzeugt index.html (self-contained Kiosk-Dashboard).
Aufruf: python3 build_dashboard.py [data.json] [index.html]
"""
import json, sys, html
from datetime import datetime
from urllib.parse import quote

DATA = sys.argv[1] if len(sys.argv) > 1 else "data.json"
OUT = sys.argv[2] if len(sys.argv) > 2 else "index.html"

with open(DATA, encoding="utf-8") as f:
    d = json.load(f)

WD = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
MON = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]

def parse(s):
    # akzeptiert 'YYYY-MM-DD' oder ISO mit Zeit/Offset
    if len(s) == 10:
        return datetime.strptime(s, "%Y-%m-%d")
    return datetime.fromisoformat(s)

def dlabel(dt):
    return f"{WD[dt.weekday()]}, {dt.day:02d}. {MON[dt.month-1]}"

def tlabel(dt):
    return f"{dt.hour:02d}:{dt.minute:02d}"

gen = parse(d["generated_at"])
gen_label = f"{dlabel(gen)} · {tlabel(gen)} Uhr"

# ---- Packliste-Karten ----
projects = sorted(d["projects"], key=lambda p: p["planperiod_start"])
total_qty = sum(p["article_total_qty"] for p in projects)
total_pos = sum(p["article_positions"] for p in projects)

def de(n):
    return f"{n:,}".replace(",", ".")

cards = []
for p in projects:
    ps = parse(p["planperiod_start"])
    pe = parse(p["planperiod_end"])
    us = parse(p["usageperiod_start"])
    ue = parse(p["usageperiod_end"])
    color = "#" + p.get("color", "FF7912")
    dry = p.get("dryhire")
    subs = p.get("subprojects", [])
    sub_html = ""
    if subs:
        chips = "".join(f'<span class="chip">{html.escape(s)}</span>' for s in subs)
        sub_html = f'<div class="subs">{chips}</div>'
    ev = dlabel(us)
    if us.date() != ue.date():
        ev = f"{dlabel(us)} – {dlabel(ue)}"
    ret = f"Rückgabe {dlabel(pe)}"
    dry_badge = '<span class="badge dry">Dry&nbsp;Hire</span>' if dry else ''
    cards.append(f"""
      <div class="card" data-raus="{p['planperiod_start']}" style="--accent:{color}">
        <div class="raus">
          <div class="raus-wd">{WD[ps.weekday()]}</div>
          <div class="raus-day">{ps.day:02d}</div>
          <div class="raus-mon">{MON[ps.month-1]}</div>
          <div class="countdown" data-raus="{p['planperiod_start']}"></div>
        </div>
        <div class="mid">
          <div class="pname">{html.escape(p['name'])} {dry_badge}</div>
          <div class="meta">{html.escape(p['customer'])} · #{p['number']}</div>
          <div class="dates">
            <span class="ico">🎪</span> Einsatz: {ev}<br>
            <span class="ico">↩︎</span> {ret}
          </div>
          {sub_html}
        </div>
        <div class="qty">
          <div class="qty-num">{de(p['article_total_qty'])}</div>
          <div class="qty-lbl">Artikel</div>
          <div class="qty-pos">{p['article_positions']} Positionen</div>
        </div>
      </div>""")

cards_html = "\n".join(cards) if cards else '<div class="empty">Keine Projekte im Zeitfenster – nichts zu packen. ☕</div>'

# ---- Kalender-Agenda (gebacken, immer sichtbar) ----
CAL_META = {
    "team": ("ZPG Team", "#FF7912"),
    "logistik": ("Logistik", "#39A0FF"),
    "abwesenheit": ("Abwesenheit", "#3ED97B"),
}
events = sorted(d.get("calendar_events", []), key=lambda e: e["start"])
by_day = {}
for e in events:
    ds = parse(e["start"]).date()
    by_day.setdefault(ds, []).append(e)

agenda_blocks = []
for day in sorted(by_day):
    dt = datetime(day.year, day.month, day.day)
    rows = []
    for e in by_day[day]:
        name, col = CAL_META.get(e["cal"], (e["cal"], "#999"))
        if e.get("allday"):
            time_html = '<span class="allday">ganztägig</span>'
        else:
            st = parse(e["start"]); en = parse(e["end"])
            time_html = f'<span class="etime">{tlabel(st)}–{tlabel(en)}</span>'
        rows.append(f"""
          <div class="event" style="--cal:{col}">
            {time_html}
            <span class="esum">{html.escape(e['summary'])}</span>
            <span class="ecal" style="background:{col}">{name}</span>
          </div>""")
    agenda_blocks.append(f"""
      <div class="agenda-day">
        <div class="aday-head">{dlabel(dt)}</div>
        {''.join(rows)}
      </div>""")

agenda_html = "\n".join(agenda_blocks) if agenda_blocks else '<div class="empty">Keine Termine in den nächsten 14 Tagen.</div>'

# ---- Google Live-Embed URL (3 Kalender kombiniert) ----
cals = d["calendars"]
def enc(x): return quote(x, safe="")
embed = ("https://calendar.google.com/calendar/embed?"
         f"src={enc(cals['team_embed_src'])}&color=%23F09300"
         f"&src={enc(cals['logistik_embed_src'])}&color=%233F51B5"
         f"&src={enc(cals['abwesenheit_embed_src'])}&color=%230B8043"
         "&ctz=Europe%2FBerlin&mode=AGENDA&wkst=2&showTitle=0&showPrint=0"
         "&showCalendars=0&showTz=0&hl=de&bgcolor=%230f1115")

HTML = f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
<title>ZPG Lager-Dashboard</title>
<style>
  :root{{ --bg:#0f1115; --panel:#171a21; --panel2:#1e222b; --txt:#f4f6fb; --mut:#9aa3b2; --org:#FF7912; --line:#2a2f3a; }}
  *{{ box-sizing:border-box; margin:0; padding:0; -webkit-tap-highlight-color:transparent; }}
  html,body{{ height:100%; }}
  body{{ font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
         background:var(--bg); color:var(--txt); overflow:hidden; }}
  .wrap{{ display:flex; flex-direction:column; height:100vh; }}

  header{{ display:flex; align-items:center; gap:20px; padding:14px 26px; background:linear-gradient(180deg,#12151c,#0f1115);
           border-bottom:2px solid var(--line); flex:0 0 auto; }}
  .logo{{ font-weight:800; font-size:26px; letter-spacing:2px; }}
  .logo b{{ color:var(--org); }}
  .logo span{{ color:var(--mut); font-weight:600; font-size:15px; letter-spacing:1px; }}
  .spacer{{ flex:1; }}
  .clock{{ font-variant-numeric:tabular-nums; font-weight:700; font-size:30px; letter-spacing:1px; }}
  .cdate{{ color:var(--mut); font-size:14px; text-align:right; }}
  .stand{{ color:var(--mut); font-size:12px; text-align:right; margin-top:2px; }}
  .live{{ display:inline-block; width:9px; height:9px; border-radius:50%; background:#3ED97B; margin-right:6px;
          box-shadow:0 0 0 0 rgba(62,217,123,.7); animation:pulse 2.2s infinite; }}
  @keyframes pulse{{ 0%{{box-shadow:0 0 0 0 rgba(62,217,123,.6)}} 70%{{box-shadow:0 0 0 12px rgba(62,217,123,0)}} 100%{{box-shadow:0 0 0 0 rgba(62,217,123,0)}} }}

  .tabs{{ display:flex; gap:10px; padding:12px 26px 0; flex:0 0 auto; }}
  .tab{{ font-size:20px; font-weight:700; padding:14px 26px; border-radius:14px 14px 0 0; background:var(--panel);
         color:var(--mut); cursor:pointer; user-select:none; border:2px solid transparent; border-bottom:none; }}
  .tab.active{{ background:var(--panel2); color:var(--txt); border-color:var(--line); }}
  .tab.active::after{{ content:""; display:block; height:3px; background:var(--org); border-radius:2px; margin-top:8px; }}
  .autobtn{{ margin-left:auto; font-size:14px; font-weight:600; color:var(--mut); background:var(--panel); border:2px solid var(--line);
             border-radius:10px; padding:8px 14px; cursor:pointer; align-self:center; }}
  .autobtn.on{{ color:#0f1115; background:var(--org); border-color:var(--org); }}

  main{{ flex:1; overflow:hidden; padding:0 26px 22px; }}
  .view{{ display:none; height:100%; background:var(--panel2); border:2px solid var(--line); border-radius:0 14px 14px 14px; overflow:hidden; }}
  .view.active{{ display:flex; flex-direction:column; }}
  .scroll{{ overflow-y:auto; padding:20px 22px; }}

  /* --- Packliste --- */
  .summary{{ display:flex; gap:26px; padding:16px 22px; border-bottom:2px solid var(--line); flex:0 0 auto; align-items:baseline; }}
  .summary .big{{ font-size:34px; font-weight:800; color:var(--org); margin-right:8px; }}
  .summary .lbl{{ font-size:15px; color:var(--mut); }}
  .summary .grp{{ display:flex; align-items:baseline; }}
  .summary .sep{{ color:var(--line); font-size:28px; }}

  .card{{ display:grid; grid-template-columns:112px 1fr 168px; gap:22px; align-items:stretch;
          background:var(--panel); border:1px solid var(--line); border-left:8px solid var(--accent);
          border-radius:14px; padding:18px 20px; margin-bottom:16px; }}
  .raus{{ text-align:center; display:flex; flex-direction:column; justify-content:center;
          background:#12151c; border-radius:12px; padding:10px 6px; }}
  .raus-wd{{ font-size:14px; color:var(--mut); font-weight:700; text-transform:uppercase; }}
  .raus-day{{ font-size:46px; font-weight:800; line-height:1; }}
  .raus-mon{{ font-size:16px; color:var(--mut); font-weight:700; text-transform:uppercase; }}
  .countdown{{ margin-top:8px; font-size:13px; font-weight:800; padding:4px 8px; border-radius:20px;
               background:#232833; color:var(--txt); }}
  .countdown.soon{{ background:#3a2a12; color:#ffb454; }}
  .countdown.now{{ background:#4a1e1e; color:#ff7a7a; }}
  .mid{{ display:flex; flex-direction:column; justify-content:center; min-width:0; }}
  .pname{{ font-size:24px; font-weight:800; line-height:1.15; }}
  .meta{{ color:var(--mut); font-size:15px; margin:4px 0 8px; }}
  .dates{{ font-size:16px; line-height:1.7; }}
  .ico{{ opacity:.8; }}
  .subs{{ margin-top:10px; display:flex; flex-wrap:wrap; gap:6px; }}
  .chip{{ font-size:12px; background:#232833; color:var(--mut); padding:4px 9px; border-radius:20px; }}
  .badge.dry{{ font-size:12px; vertical-align:middle; background:#2a3550; color:#8fb8ff; padding:3px 9px; border-radius:6px; font-weight:700; }}
  .qty{{ display:flex; flex-direction:column; justify-content:center; align-items:center; text-align:center;
         background:#12151c; border-radius:12px; }}
  .qty-num{{ font-size:52px; font-weight:800; color:var(--org); line-height:1; }}
  .qty-lbl{{ font-size:15px; color:var(--mut); font-weight:700; text-transform:uppercase; letter-spacing:1px; }}
  .qty-pos{{ font-size:13px; color:var(--mut); margin-top:8px; }}
  .empty{{ text-align:center; color:var(--mut); font-size:22px; padding:60px 20px; }}

  /* --- Agenda --- */
  .agenda-day{{ margin-bottom:22px; }}
  .aday-head{{ font-size:18px; font-weight:800; color:var(--org); padding-bottom:8px; border-bottom:1px solid var(--line); margin-bottom:10px; }}
  .event{{ display:flex; align-items:center; gap:14px; padding:11px 12px; border-left:4px solid var(--cal);
           background:var(--panel); border-radius:8px; margin-bottom:8px; }}
  .etime,.allday{{ font-variant-numeric:tabular-nums; font-weight:700; min-width:120px; color:var(--txt); font-size:16px; }}
  .allday{{ color:var(--mut); }}
  .esum{{ flex:1; font-size:17px; }}
  .ecal{{ font-size:12px; font-weight:700; color:#0f1115; padding:3px 10px; border-radius:20px; }}

  iframe{{ width:100%; height:100%; border:0; background:#0f1115; }}
  .embed-hint{{ font-size:13px; color:var(--mut); padding:10px 22px; border-bottom:1px solid var(--line); flex:0 0 auto; }}
  .embed-hint b{{ color:var(--txt); }}
  ::-webkit-scrollbar{{ width:10px; }} ::-webkit-scrollbar-thumb{{ background:#2c313c; border-radius:6px; }}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div class="logo"><b>ZPG</b> LAGER <span>· Dashboard</span></div>
    <div class="spacer"></div>
    <div>
      <div class="clock" id="clock">--:--:--</div>
      <div class="cdate" id="cdate"></div>
      <div class="stand"><span class="live"></span>Stand: {gen_label}</div>
    </div>
  </header>

  <div class="tabs">
    <div class="tab active" data-view="pack">📦 Zu packen</div>
    <div class="tab" data-view="cal">📅 Kalender</div>
    <div class="tab" data-view="live">🗓️ Live-Kalender</div>
    <button class="autobtn" id="autobtn">⟳ Auto-Wechsel</button>
  </div>

  <main>
    <!-- Packliste -->
    <section class="view active" id="pack">
      <div class="summary">
        <div class="grp"><span class="big">{len(projects)}</span> <span class="lbl">Projekte</span></div>
        <div class="sep">|</div>
        <div class="grp"><span class="big">{de(total_qty)}</span> <span class="lbl">Artikel gesamt</span></div>
        <div class="sep">|</div>
        <div class="grp"><span class="big">{total_pos}</span> <span class="lbl">Positionen</span></div>
        <div class="sep">|</div>
        <div class="lbl">nächste 2 Wochen · Auszug (planperiod)</div>
      </div>
      <div class="scroll">
        {cards_html}
      </div>
    </section>

    <!-- Kalender gebacken -->
    <section class="view" id="cal">
      <div class="scroll">
        {agenda_html}
      </div>
    </section>

    <!-- Live Google Kalender -->
    <section class="view" id="live">
      <div class="embed-hint">Live aus Google Kalender (Team · Logistik · Abwesenheit). <b>Hinweis:</b> Zeigt nur Termine, wenn das Gerät in einem ZPG-Google-Konto angemeldet ist oder die Kalender öffentlich freigegeben sind.</div>
      <iframe id="gcal" loading="lazy" src=""></iframe>
    </section>
  </main>
</div>

<script>
  var EMBED = "{embed}";
  // Uhr
  var days=["Sonntag","Montag","Dienstag","Mittwoch","Donnerstag","Freitag","Samstag"];
  var mons=["Januar","Februar","März","April","Mai","Juni","Juli","August","September","Oktober","November","Dezember"];
  function tick(){{ var n=new Date();
    document.getElementById('clock').textContent =
      String(n.getHours()).padStart(2,'0')+":"+String(n.getMinutes()).padStart(2,'0')+":"+String(n.getSeconds()).padStart(2,'0');
    document.getElementById('cdate').textContent = days[n.getDay()]+", "+n.getDate()+". "+mons[n.getMonth()]+" "+n.getFullYear();
  }}
  tick(); setInterval(tick,1000);

  // Countdown je Karte (live berechnet)
  function midnight(d){{ return new Date(d.getFullYear(),d.getMonth(),d.getDate()); }}
  function updateCountdowns(){{
    var now=midnight(new Date());
    document.querySelectorAll('.countdown').forEach(function(el){{
      var r=midnight(new Date(el.getAttribute('data-raus')));
      var diff=Math.round((r-now)/86400000);
      var t, cls='';
      if(diff<0){{ t='läuft'; }}
      else if(diff===0){{ t='HEUTE'; cls='now'; }}
      else if(diff===1){{ t='MORGEN'; cls='soon'; }}
      else if(diff<=3){{ t='in '+diff+' Tagen'; cls='soon'; }}
      else {{ t='in '+diff+' Tagen'; }}
      el.textContent=t; el.className='countdown '+cls;
    }});
  }}
  updateCountdowns(); setInterval(updateCountdowns,3600000);

  // Tabs
  var tabs=document.querySelectorAll('.tab'), views=document.querySelectorAll('.view');
  function show(v){{
    tabs.forEach(function(t){{ t.classList.toggle('active', t.getAttribute('data-view')===v); }});
    views.forEach(function(s){{ s.classList.toggle('active', s.id===v); }});
    if(v==='live'){{ var f=document.getElementById('gcal'); if(!f.src||f.src==='about:blank'||f.src===''){{ f.src=EMBED; }} }}
  }}
  tabs.forEach(function(t){{ t.addEventListener('click', function(){{ stopAuto(); show(t.getAttribute('data-view')); }}); }});

  // Auto-Wechsel zwischen Packen & Kalender
  var autoTimer=null, order=['pack','cal'], idx=0;
  var btn=document.getElementById('autobtn');
  function startAuto(){{ btn.classList.add('on'); idx=0; show(order[0]);
    autoTimer=setInterval(function(){{ idx=(idx+1)%order.length; show(order[idx]); }}, 20000); }}
  function stopAuto(){{ if(autoTimer){{ clearInterval(autoTimer); autoTimer=null; }} btn.classList.remove('on'); }}
  btn.addEventListener('click', function(e){{ e.stopPropagation(); if(autoTimer) stopAuto(); else startAuto(); }});

  // Seite regelmäßig neu laden, damit aktualisierte Daten übernommen werden (alle 15 Min)
  setTimeout(function(){{ location.reload(); }}, 15*60*1000);
</script>
</body>
</html>
"""

with open(OUT, "w", encoding="utf-8") as f:
    f.write(HTML)
print("geschrieben:", OUT, "-", len(HTML), "bytes")
