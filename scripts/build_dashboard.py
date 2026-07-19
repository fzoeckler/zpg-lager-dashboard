#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ZPG Lager-Dashboard Generator.
Liest data.json und erzeugt index.html (self-contained Kiosk-Dashboard).
Aufruf: python3 build_dashboard.py [data.json] [index.html]
"""
import json, sys, html
from datetime import datetime, timedelta
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
    "team": ("ZPG Team", "#15C7DE"),
    "logistik": ("Logistik", "#5B8DEF"),
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

# ---- Gantt / Zeitstrahl (kommende Projekte, bestätigt + Option) ----
def iso_kw(dt):
    return dt.isocalendar()[1]

upcoming = sorted(d.get("upcoming", []), key=lambda p: p["planperiod_start"])
gwin_start = datetime(gen.year, gen.month, gen.day)
_ws = d.get("upcoming_window_start")
if _ws:
    p0 = parse(_ws); gwin_start = datetime(p0.year, p0.month, p0.day)
_we = d.get("upcoming_window_end")
gwin_end = parse(_we) if _we else (gwin_start + timedelta(days=56))
gwin_end = datetime(gwin_end.year, gwin_end.month, gwin_end.day)
gtotal = max((gwin_end - gwin_start).days, 1)

def gpct(dt):
    v = (datetime(dt.year, dt.month, dt.day, dt.hour, dt.minute) - gwin_start).total_seconds() / (gtotal * 86400) * 100
    return max(0.0, min(100.0, v))

# Wochenend-Schattierung + Wochen-Gitter/Header
bands = []
weekticks = []
weeklabels = []
day = gwin_start
while day < gwin_end:
    if day.weekday() >= 5:
        l = gpct(day); w = gpct(day + timedelta(days=1)) - l
        bands.append(f'<div class="band" style="left:{l:.3f}%;width:{w:.3f}%"></div>')
    if day.weekday() == 0:  # Montag -> Wochenmarke
        l = gpct(day)
        weekticks.append(f'<div class="wtick" style="left:{l:.3f}%"></div>')
        weeklabels.append(f'<div class="wlabel" style="left:{l:.3f}%">KW{iso_kw(day):02d}<span>{day.day:02d}.{day.month:02d}</span></div>')
    day += timedelta(days=1)
today_left = gpct(datetime(gen.year, gen.month, gen.day, gen.hour, gen.minute))
today_line = f'<div class="today" style="left:{today_left:.3f}%"></div>'
today_lbl = f'<div class="today-lbl" style="left:{today_left:.3f}%">heute</div>'

grows = []
for p in upcoming:
    s = parse(p["planperiod_start"]); e = parse(p["planperiod_end"])
    l = gpct(s); r = gpct(e); w = max(r - l, 1.4)
    is_opt = str(p.get("status", "")).lower().startswith("opt")
    cls = "opt" if is_opt else "conf"
    us = parse(p["usageperiod_start"]); ue = parse(p["usageperiod_end"])
    ev = dlabel(us) if us.date() == ue.date() else f"{dlabel(us)}–{dlabel(ue)}"
    title = f"{p['name']} · {p.get('customer','')} · Auszug {dlabel(s)}–{dlabel(e)} · Einsatz {ev}"
    label = html.escape(p["name"])
    grows.append(f"""
      <div class="grow">
        <div class="glabel" title="{html.escape(title)}">{label}</div>
        <div class="gtrack">
          <div class="gbar {cls}" style="left:{l:.3f}%;width:{w:.3f}%" title="{html.escape(title)}">
            <span class="gbar-txt">{label}</span>
          </div>
        </div>
      </div>""")

if upcoming:
    n_conf = sum(1 for p in upcoming if not str(p.get("status","")).lower().startswith("opt"))
    n_opt = len(upcoming) - n_conf
    gantt_html = f"""
      <div class="gantt-head">
        <div class="glabel head">Projekt</div>
        <div class="gtrack head">
          {''.join(bands)}
          {''.join(weekticks)}
          {''.join(weeklabels)}
          {today_line}{today_lbl}
        </div>
      </div>
      <div class="gantt-body">
        <div class="gantt-bands">{''.join(bands)}{''.join(weekticks)}{today_line}</div>
        {''.join(grows)}
      </div>"""
    gantt_summary = f'<span class="big">{len(upcoming)}</span> <span class="lbl">Projekte</span> &nbsp;·&nbsp; <span class="dot conf"></span>{n_conf} bestätigt &nbsp; <span class="dot opt"></span>{n_opt} Option &nbsp;·&nbsp; <span class="lbl">{dlabel(gwin_start)} – {dlabel(gwin_end)}</span>'
else:
    gantt_html = '<div class="empty">Noch keine kommenden Projekte geladen.<br><span style="font-size:15px">Wird beim nächsten Datenlauf aus Rentman befüllt.</span></div>'
    gantt_summary = '<span class="lbl">Zeitstrahl wird beim nächsten Rentman-Datenlauf befüllt.</span>'

# ---- Rückläufer / Retour (Rückgabe im 14-Tage-Fenster) ----
def qty_block(p):
    if p.get("article_total_qty") is None:
        return ""
    return f"""<div class="qty">
          <div class="qty-num">{de(p['article_total_qty'])}</div>
          <div class="qty-lbl">Artikel</div>
          <div class="qty-pos">{p.get('article_positions','?')} Positionen</div>
        </div>"""

returns = sorted(d.get("returns", []), key=lambda p: p["planperiod_end"])
rcards = []
for p in returns:
    pe = parse(p["planperiod_end"])
    us = parse(p["usageperiod_start"]); ue = parse(p["usageperiod_end"])
    color = "#" + p.get("color", "15C7DE")
    ev = dlabel(us) if us.date() == ue.date() else f"{dlabel(us)} – {dlabel(ue)}"
    has_qty = p.get("article_total_qty") is not None
    grid = "112px 1fr 168px" if has_qty else "112px 1fr"
    rcards.append(f"""
      <div class="card" style="--accent:{color};grid-template-columns:{grid}">
        <div class="raus ret">
          <div class="raus-wd">{WD[pe.weekday()]}</div>
          <div class="raus-day">{pe.day:02d}</div>
          <div class="raus-mon">{MON[pe.month-1]}</div>
          <div class="countdown" data-raus="{p['planperiod_end']}"></div>
        </div>
        <div class="mid">
          <div class="pname">{html.escape(p['name'])}</div>
          <div class="meta">{html.escape(p.get('customer',''))} · #{p.get('number','')}</div>
          <div class="dates"><span class="ico">↩︎</span> Rückgabe {dlabel(pe)} · {tlabel(pe)} Uhr<br><span class="ico">🎪</span> Einsatz war: {ev}</div>
        </div>
        {qty_block(p)}
      </div>""")
if "returns" not in d:
    returns_html = '<div class="empty">Rückläufer werden beim nächsten Datenlauf aus Rentman befüllt.</div>'
    returns_summary = '<span class="lbl">Wird beim nächsten Rentman-Datenlauf befüllt.</span>'
elif not returns:
    returns_html = '<div class="empty">Keine Rückläufer in den nächsten 14 Tagen. ☕</div>'
    returns_summary = '<span class="lbl">nächste 2 Wochen · keine Rückgaben fällig</span>'
else:
    rq = sum(p.get("article_total_qty") or 0 for p in returns)
    returns_html = "\n".join(rcards)
    returns_summary = f'<span class="big">{len(returns)}</span> <span class="lbl">Rückläufer</span> &nbsp;·&nbsp; <span class="big">{de(rq)}</span> <span class="lbl">Artikel einzuchecken</span> &nbsp;·&nbsp; <span class="lbl">nächste 2 Wochen · Rückgabe (planperiod)</span>'

# ---- Engpässe / Fehlmengen (has_missings) ----
shortages = sorted(d.get("shortages", []), key=lambda s: s.get("planperiod_start", "9999"))
scards = []
for s in shortages:
    ps = parse(s["planperiod_start"]) if s.get("planperiod_start") else None
    color = "#" + s.get("color", "15C7DE")
    items = s.get("items", [])
    chips = "".join(
        f'<span class="mchip">{html.escape(str(it.get("name","?")))}'
        + (f' <b>−{it["short"]}</b>' if it.get("short") is not None else '')
        + '</span>'
        for it in items)
    when = f'Auszug {dlabel(ps)}' if ps else ''
    ncount = s.get("missing_count", len(items))
    scards.append(f"""
      <div class="scard" style="--accent:{color}">
        <div class="shead">
          <div>
            <div class="pname">{html.escape(s['name'])}</div>
            <div class="meta">{html.escape(s.get('customer',''))} · #{s.get('number','')} · {when}</div>
          </div>
          <div class="sbadge">{ncount} Fehlmengen</div>
        </div>
        <div class="mitems">{chips if chips else '<span class="mchip">Details siehe Rentman</span>'}</div>
      </div>""")
if "shortages" not in d:
    shortages_html = '<div class="empty">Engpässe werden beim nächsten Datenlauf aus Rentman befüllt.</div>'
    shortages_summary = '<span class="lbl">Wird beim nächsten Rentman-Datenlauf befüllt.</span>'
elif not shortages:
    shortages_html = '<div class="empty ok">Keine Materialengpässe in kommenden Projekten. 👍</div>'
    shortages_summary = '<span class="lbl">kommende Projekte · keine Unterdeckung gemeldet</span>'
else:
    tot_missing = sum(s.get("missing_count", len(s.get("items", []))) for s in shortages)
    shortages_html = "\n".join(scards)
    shortages_summary = f'<span class="big warn">{len(shortages)}</span> <span class="lbl">Projekte mit Engpass</span> &nbsp;·&nbsp; <span class="big warn">{tot_missing}</span> <span class="lbl">Fehlmengen gesamt</span> &nbsp;·&nbsp; <span class="lbl">→ anmieten / umplanen</span>'

# ---- Google Live-Embed URL (3 Kalender kombiniert) ----
cals = d["calendars"]
def enc(x): return quote(x, safe="")
embed = ("https://calendar.google.com/calendar/embed?"
         f"src={enc(cals['team_embed_src'])}&color=%2315889B"
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
  :root{{ --bg:#0f1115; --panel:#171a21; --panel2:#1e222b; --txt:#f4f6fb; --mut:#9aa3b2; --org:#15C7DE; --org-dim:#0e7f8f; --line:#2a2f3a; }}
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
  .empty.ok{{ color:#3ED97B; }}

  /* --- Rückläufer --- */
  .raus.ret .raus-day{{ color:#8fe3ff; }}

  /* --- Engpässe / Fehlmengen --- */
  .big.warn{{ color:#ffb454; }}
  .scard{{ background:var(--panel); border:1px solid var(--line); border-left:8px solid var(--accent);
           border-radius:14px; padding:16px 20px; margin-bottom:14px; }}
  .shead{{ display:flex; align-items:center; justify-content:space-between; gap:16px; }}
  .sbadge{{ flex:0 0 auto; font-size:15px; font-weight:800; color:#1a1205; background:#ffb454;
            padding:6px 14px; border-radius:20px; white-space:nowrap; }}
  .mitems{{ margin-top:12px; display:flex; flex-wrap:wrap; gap:8px; }}
  .mchip{{ font-size:14px; background:#3a2a12; color:#ffcf8a; border:1px solid #5a3f18;
           padding:6px 12px; border-radius:8px; }}
  .mchip b{{ color:#ff8a5c; font-weight:800; }}

  /* --- Agenda --- */
  .agenda-day{{ margin-bottom:22px; }}
  .aday-head{{ font-size:18px; font-weight:800; color:var(--org); padding-bottom:8px; border-bottom:1px solid var(--line); margin-bottom:10px; }}
  .event{{ display:flex; align-items:center; gap:14px; padding:11px 12px; border-left:4px solid var(--cal);
           background:var(--panel); border-radius:8px; margin-bottom:8px; }}
  .etime,.allday{{ font-variant-numeric:tabular-nums; font-weight:700; min-width:120px; color:var(--txt); font-size:16px; }}
  .allday{{ color:var(--mut); }}
  .esum{{ flex:1; font-size:17px; }}
  .ecal{{ font-size:12px; font-weight:700; color:#0f1115; padding:3px 10px; border-radius:20px; }}

  /* --- Gantt / Zeitplan --- */
  #plan .scroll{{ padding:0; }}
  .gantt-head{{ display:flex; position:sticky; top:0; z-index:5; background:var(--panel2);
                border-bottom:2px solid var(--line); height:52px; }}
  .glabel{{ flex:0 0 250px; padding:10px 14px; font-size:15px; color:var(--txt); overflow:hidden;
            text-overflow:ellipsis; white-space:nowrap; border-right:1px solid var(--line); }}
  .glabel.head{{ font-weight:800; color:var(--mut); display:flex; align-items:center; }}
  .gtrack{{ position:relative; flex:1; height:100%; overflow:hidden; }}
  .gtrack.head{{ height:52px; }}
  .band{{ position:absolute; top:0; bottom:0; background:rgba(255,255,255,.035); }}
  .wtick{{ position:absolute; top:0; bottom:0; width:1px; background:var(--line); }}
  .wlabel{{ position:absolute; top:8px; transform:translateX(4px); font-size:12px; font-weight:700; color:var(--mut); white-space:nowrap; }}
  .wlabel span{{ display:block; font-size:10px; font-weight:600; color:#6b7482; }}
  .today{{ position:absolute; top:0; bottom:0; width:2px; background:var(--org); z-index:4; box-shadow:0 0 8px var(--org); }}
  .today-lbl{{ position:absolute; top:6px; transform:translateX(-50%); font-size:11px; font-weight:800; color:#0f1115;
               background:var(--org); padding:2px 7px; border-radius:10px; z-index:6; }}
  .gantt-body{{ position:relative; }}
  .gantt-bands{{ position:absolute; inset:0; left:250px; pointer-events:none; }}
  .grow{{ display:flex; align-items:center; height:40px; border-bottom:1px solid rgba(255,255,255,.04); }}
  .grow .glabel{{ color:var(--mut); font-size:14px; }}
  .gbar{{ position:absolute; top:7px; height:26px; border-radius:7px; display:flex; align-items:center;
          padding:0 10px; overflow:hidden; z-index:2; }}
  .gbar.conf{{ background:linear-gradient(180deg,var(--org),var(--org-dim)); }}
  .gbar.opt{{ background:repeating-linear-gradient(45deg,rgba(21,199,222,.18),rgba(21,199,222,.18) 6px,rgba(21,199,222,.06) 6px,rgba(21,199,222,.06) 12px);
              border:1.5px dashed var(--org); }}
  .gbar-txt{{ font-size:13px; font-weight:700; color:#08222a; white-space:nowrap; text-overflow:ellipsis; overflow:hidden; }}
  .gbar.opt .gbar-txt{{ color:var(--txt); }}
  .plan-summary{{ display:flex; align-items:center; gap:6px; padding:14px 22px; border-bottom:2px solid var(--line); flex:0 0 auto; font-size:15px; color:var(--mut); }}
  .plan-summary .big{{ font-size:30px; font-weight:800; color:var(--org); }}
  .dot{{ display:inline-block; width:13px; height:13px; border-radius:3px; margin:0 4px -1px 8px; }}
  .dot.conf{{ background:linear-gradient(180deg,var(--org),var(--org-dim)); }}
  .dot.opt{{ background:repeating-linear-gradient(45deg,rgba(21,199,222,.25),rgba(21,199,222,.25) 4px,rgba(21,199,222,.08) 4px,rgba(21,199,222,.08) 8px); border:1.5px dashed var(--org); }}

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
    <div class="tab" data-view="returns">📥 Rückläufer</div>
    <div class="tab" data-view="short">⚠️ Engpässe</div>
    <div class="tab" data-view="plan">📊 Zeitplan</div>
    <div class="tab" data-view="cal">📅 Kalender</div>
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

    <!-- Rückläufer / Retour -->
    <section class="view" id="returns">
      <div class="summary">{returns_summary}</div>
      <div class="scroll">
        {returns_html}
      </div>
    </section>

    <!-- Engpässe / Fehlmengen -->
    <section class="view" id="short">
      <div class="summary">{shortages_summary}</div>
      <div class="scroll">
        {shortages_html}
      </div>
    </section>

    <!-- Zeitplan / Gantt -->
    <section class="view" id="plan">
      <div class="plan-summary">{gantt_summary}</div>
      <div class="scroll">
        {gantt_html}
      </div>
    </section>

    <!-- Kalender gebacken -->
    <section class="view" id="cal">
      <div class="scroll">
        {agenda_html}
      </div>
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
  var autoTimer=null, order=['pack','plan','cal'], idx=0;
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
