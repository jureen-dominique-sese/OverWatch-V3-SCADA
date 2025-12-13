"""
Overwatch SCADA - Enhanced with Multiple Map Types & Transmission Linessad
"""
import webview
import requests
import csv
import io
from datetime import datetime, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import asyncio
from telegram import Bot
from telegram.error import TelegramError

SHEET_ID = "1f1OMSgWDZs7p7oxvsLQhNiWytlKpWaj1PLIOQgJKyKU"
SHEET_NAME = "logger"
CREDENTIALS_FILE = "credentials.json"

# TELEGRAM CONFIGURATION
TELEGRAM_BOT_TOKEN = "7853460988:AAH3eIhrYLcu9gmVzVu2Xq-hAgs1pUJk-wU"  # Replace with your bot token from @BotFather
TELEGRAM_CHAT_IDS = ["6493927838"]  # Replace with your chat ID from @userinfobot


class Api:
    def __init__(self):
        self.cache = []
        self.gc = None
        self.worksheet = None
        self.telegram_enabled = False
        self.last_alerted_faults = set()  # Track which faults we've already alerted
        self._init_gspread()
        self._init_telegram()

    def _init_gspread(self):
        """Initialize Google Sheets connection"""
        try:
            scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
            creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
            self.gc = gspread.authorize(creds)
            self.worksheet = self.gc.open_by_key(SHEET_ID).worksheet(SHEET_NAME)
            print("✓ Connected to Google Sheets")
        except Exception as e:
            print(f"⚠ Google Sheets connection failed: {e}")

    def _init_telegram(self):
        """Initialize Telegram bot"""
        try:
            if TELEGRAM_BOT_TOKEN != "YOUR_BOT_TOKEN_HERE" and TELEGRAM_CHAT_IDS[0] != "YOUR_CHAT_ID_HERE":
                # Test the bot connection
                asyncio.run(self._test_telegram_connection())
                self.telegram_enabled = True
                print("✓ Telegram bot initialized and ready")
            else:
                print("⚠ Telegram not configured - update TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_IDS")
        except Exception as e:
            print(f"⚠ Telegram initialization failed: {e}")
            self.telegram_enabled = False

    async def _test_telegram_connection(self):
        """Test if telegram bot token is valid"""
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        bot_info = await bot.get_me()
        print(f"✓ Bot connected: @{bot_info.username}")

    async def _send_telegram_message(self, fault):
        """Send telegram alert for a fault (async)"""
        try:
            bot = Bot(token=TELEGRAM_BOT_TOKEN)
            
            # Severity emoji mapping
            severity_emoji = {
                "CRITICAL": "🔴",
                "WARNING": "🟡",
                "INFO": "🔵"
            }
            
            # Format the alert message
            message = (
                f"⚡ *FAULT DETECTION SYSTEM ALERT*\n"
                f"{'═' * 35}\n\n"
                f"🔴 *SEVERITY LEVEL:* {fault['sev']}\n"
                f"📋 *REPORT ID:* `{fault['id']}`\n"
                f"⏰ *TIMESTAMP:* {fault['date']} @ {fault['time']}\n\n"
                f"🏭 *EQUIPMENT DETAILS*\n"
                f"├─ Device: {fault['device']}\n"
                f"├─ Fault Distance: {fault['dist']}m\n"
                f"└─ GPS Coordinates: {fault['lat']}, {fault['lng']}\n\n"
                f"📍 *LOCATION MAPPING*\n"
                f"[View Fault Location on Map](https://www.google.com/maps?q={fault['lat']},{fault['lng']})\n\n"
                f"⚠️ *ACTION REQUIRED*\n"
                f"Immediate investigation and acknowledgment needed.\n"
                f"Dispatch field crew to affected area.\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"_Overwatch SCADA System_\n"
                f"_(c) 2025, Delas Llagas, Sese, Valenzuela_"
            )
            
            # Send to all configured chat IDs
            for chat_id in TELEGRAM_CHAT_IDS:
                try:
                    await bot.send_message(
                        chat_id=chat_id,
                        text=message,
                        parse_mode='Markdown',
                        disable_web_page_preview=False
                    )
                    print(f"✓ Telegram alert sent to chat {chat_id} for fault {fault['id']}")
                except TelegramError as e:
                    print(f"✗ Failed to send to {chat_id}: {e}")
                    
        except Exception as e:
            print(f"❌ Telegram send error: {e}")

    def send_telegram_alert(self, fault):
        """Synchronous wrapper for sending telegram alerts"""
        if not self.telegram_enabled:
            print("⚠ Telegram alerts disabled - check configuration")
            return {"ok": False, "err": "Telegram not enabled"}
        
        try:
            # Run async function in new event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._send_telegram_message(fault))
            loop.close()
            return {"ok": True}
        except Exception as e:
            print(f"❌ Error sending Telegram alert: {e}")
            return {"ok": False, "err": str(e)}

    def get_faults(self):
        """Fetch faults from Google Sheets and send alerts for new ones"""
        url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={SHEET_NAME}"
        try:
            response = requests.get(url, timeout=2)
            response.raise_for_status()
            reader = csv.reader(io.StringIO(response.text))
            next(reader)  # Skip header
            data = []

            existing_ids = {f['id'] for f in self.cache}

            for row in reader:
                try:
                    if len(row) < 7:
                        continue
                        
                    dist = float(row[4])
                    if dist > 100000:
                        sev = "CRITICAL"
                    elif dist > 20000:
                        sev = "WARNING"
                    elif dist > 5000:
                        sev = "CAUTION"
                    else:
                        sev = "INFO"
                    status = row[7] if len(row) > 7 else ""
                    
                    fault = {
                        "id": row[0],
                        "date": row[1],
                        "time": row[2],
                        "device": row[3],
                        "dist": dist,
                        "lat": float(row[5]),
                        "lng": float(row[6]),
                        "status": status,
                        "mod": row[8] if len(row) > 8 else "",
                        "ack": status.lower() in ["acknowledged", "resolved", "fixed"],
                        "sev": sev
                    }
                    data.append(fault)
                    
                    # 🔔 AUTO TELEGRAM ALERT LOGIC
                    # Send alert ONLY for NEW faults (not in existing_ids)
                    # and only if CRITICAL or WARNING and not acknowledged
                    if (fault['id'] not in existing_ids and 
                        fault['sev'] in ["CRITICAL", "WARNING"] and 
                        not fault['ack']):
                        
                        fault_key = f"{fault['id']}_{fault['date']}_{fault['time']}"
                        if fault_key not in self.last_alerted_faults:
                            print(f"🔔 New {fault['sev']} fault detected: {fault['id']}")
                            self.send_telegram_alert(fault)
                            self.last_alerted_faults.add(fault_key)
                            
                except Exception as e:
                    print(f"⚠ Error processing row: {e}")
                    continue
                    
            self.cache = data
            return data
            
        except Exception as e:
            print(f"⚠ Error fetching faults: {e}")
            return self.cache

    def ack_fault(self, rid, status, name):
        """Acknowledge a fault by updating Google Sheets"""
        if not self.worksheet:
            return {"ok": False, "err": "Not connected to Google Sheets"}
        try:
            cell = self.worksheet.find(rid)
            if not cell:
                return {"ok": False, "err": "Report ID not found"}
            
            self.worksheet.update_cell(cell.row, 8, status)
            self.worksheet.update_cell(cell.row, 9, name)
            print(f"✓ Fault {rid} acknowledged by {name} - Status: {status}")
            
            return {"ok": True}
        except Exception as e:
            print(f"❌ Acknowledgement error: {e}")
            return {"ok": False, "err": str(e)}

    def get_stats(self):
        """Generate statistics from cached fault data"""
        if not self.cache:
            return {}
            
        today = datetime.now().date()
        week_ago = today - timedelta(days=7)
        
        stats = {
            "total": len(self.cache),
            "today": 0,
            "week": 0,
            "ack": 0,
            "pend": 0,
            "crit": 0,
            "warn": 0,
            "info": 0,
            "caution": 0,  # ← ADD THIS
            "devs": {}
        }
        
        for f in self.cache:
            try:
                fd = datetime.strptime(f["date"], "%Y-%m-%d").date()
                
                if fd == today:
                    stats["today"] += 1
                if fd >= week_ago:
                    stats["week"] += 1
                    
                stats["ack" if f["ack"] else "pend"] += 1
                
                severity_map = {"CRITICAL": "crit", "WARNING": "warn", "CAUTION": "caution", "INFO": "info"}
                stats[severity_map[f["sev"]]] += 1
                
                stats["devs"][f["device"]] = stats["devs"].get(f["device"], 0) + 1
            except:
                pass
                
        return stats
    
    def get_telegram_status(self):
        """Get telegram configuration status for UI"""
        return {
            "enabled": self.telegram_enabled,
            "bot_configured": TELEGRAM_BOT_TOKEN != "YOUR_BOT_TOKEN_HERE",
            "chat_configured": TELEGRAM_CHAT_IDS[0] != "YOUR_CHAT_ID_HERE",
            "chat_ids": TELEGRAM_CHAT_IDS if self.telegram_enabled else [],
            "alerts_sent": len(self.last_alerted_faults)
        }
    
    def test_telegram(self):
        """Send a test Telegram message"""
        if not self.telegram_enabled:
            return {"ok": False, "err": "Telegram not configured"}
        
        test_fault = {
            "id": "TEST-001",
            "device": "Test Device",
            "dist": 1500,
            "sev": "WARNING",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "time": datetime.now().strftime("%H:%M:%S"),
            "lat": 13.621775,
            "lng": 123.194824
        }
        
        print("📤 Sending test Telegram alert...")
        return self.send_telegram_alert(test_fault)


HTML = """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Overwatch SCADA</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.css">
<script src="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
/* DISPATCH SYSTEM STYLES */
.crew-list { display:flex; flex-direction:column; gap:8px; margin-top:16px; }
.crew-card { padding:10px; border:1px solid #e5e7eb; border-radius:8px; display:flex; align-items:center; justify-content:space-between; font-size:13px; }
.crew-status { width:8px; height:8px; border-radius:50%; background:var(--sub); }
.crew-status.idle { background:var(--green); }
.crew-status.busy { background:var(--amber); }

/* FLEET DASHBOARD GRID */
.stat-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:20px; margin-bottom:30px; }
.s-card { background:white; padding:20px; border-radius:12px; border-left:4px solid var(--sub); }

/* DISPATCH MODAL */
.modal-wrap { position:fixed; inset:0; background:rgba(0,0,0,0.5); z-index:3000; display:none; align-items:center; justify-content:center; }
.modal { background:white; padding:24px; border-radius:12px; width:400px; }
.btn-d { background:var(--red); color:white; width:100%; margin-top:8px; }
:root{--bg:#1e1e1e;--bg-secondary:#252526;--bg-tertiary:#2d2d30;--panel:#252526;--text:#cccccc;--text-secondary:#858585;--border:#3e3e42;--accent:#007acc;--accent-hover:#1c97ea;--crit:#f48771;--warn:#cca700;--info:#4fc1ff;--ok:#89d185;--caution:#ff9800;--input-bg:#3c3c3c}
[dark]{--bg:#0d1117;--bg-secondary:#161b22;--bg-tertiary:#21262d;--panel:#161b22;--border:#30363d;--accent:#58a6ff;--input-bg:#0d1117}
*{margin:0;padding:0;box-sizing:border-box;font-family:'Segoe UI',Consolas,'Courier New',monospace}
body{background:var(--bg);color:var(--text);overflow:hidden;font-size:13px;line-height:1.5}
.top{background:var(--bg-secondary);border-bottom:1px solid var(--border);padding:0 20px;height:48px;display:flex;align-items:center;gap:20px}
.top-title{font-weight:500;color:var(--text);margin-right:auto;font-size:13px;letter-spacing:0.3px;display:flex;align-items:center;gap:8px}
.top-btn{padding:8px 16px;cursor:pointer;border-radius:2px;font-size:12px;color:var(--text-secondary);transition:all 0.15s;border:1px solid transparent;font-weight:400}
.top-btn:hover{background:var(--bg-tertiary);color:var(--text);border-color:var(--border)}
.tabs{background:var(--bg-secondary);border-bottom:1px solid var(--border);display:flex;padding:0 20px;gap:2px}
.tab{padding:12px 20px;cursor:pointer;border-bottom:2px solid transparent;font-size:13px;color:var(--text-secondary);transition:all 0.15s;font-weight:400}
.tab:hover{background:var(--bg-tertiary);color:var(--text)}
.tab.on{color:var(--accent);border-bottom-color:var(--accent);background:var(--bg)}
.main{display:flex;height:calc(100vh - 80px)}
.content{display:none;flex:1}
.content.on{display:flex}
.map-view{display:flex;width:100%;position:relative;background:var(--bg)}
#map{flex:1;margin-bottom:91px}  /* Changed from 31px to 91px (31 + 60) */
.map-ctrl{position:absolute;top:16px;right:380px;z-index:1000;background:var(--panel);border-radius:3px;border:1px solid var(--border);box-shadow:0 4px 12px rgba(0,0,0,0.5);overflow:hidden;min-width:200px}
.map-ctrl-title{padding:10px 14px;background:var(--bg-tertiary);color:var(--text);font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:0.5px;border-bottom:1px solid var(--border)}
.map-ctrl-opt{padding:10px 14px;cursor:pointer;font-size:12px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:10px;color:var(--text);transition:background 0.15s}
.map-ctrl-opt:last-child{border-bottom:none}
.map-ctrl-opt:hover{background:var(--bg-tertiary)}
.map-ctrl-opt.on{background:var(--bg-tertiary);color:var(--accent);border-left:2px solid var(--accent);padding-left:12px}
.side{width:360px;background:var(--panel);border-left:1px solid var(--border);overflow-y:auto;padding:20px;display:flex;flex-direction:column;gap:20px}
.side h3{font-size:12px;color:var(--text-secondary);text-transform:uppercase;letter-spacing:0.5px;margin-bottom:12px;font-weight:600}
.box{background:var(--bg-tertiary);border-radius:3px;padding:14px;font-size:12px;line-height:1.6;border:1px solid var(--border)}
.box strong{color:var(--accent);font-weight:600}
.btn{width:100%;padding:10px;border:1px solid var(--border);border-radius:3px;cursor:pointer;font-size:12px;font-weight:500;margin-top:8px;transition:all 0.15s;background:var(--bg-tertiary);color:var(--text)}
.btn:hover{background:var(--accent);color:#fff;border-color:var(--accent)}
.btn-1{background:var(--accent);color:#fff;border-color:var(--accent)}
.btn-1:hover{background:var(--accent-hover)}
.btn-2{background:var(--bg-tertiary);color:var(--text)}
.btn-2:hover{background:var(--input-bg)}
.btn-ok{background:var(--ok);color:#000;border-color:var(--ok);font-weight:600}
.btn-ok:hover{opacity:0.85}
.tog{display:flex;align-items:center;justify-content:center;gap:8px;background:var(--input-bg);border-color:var(--border)}
.tog.on{background:var(--ok);color:#000;border-color:var(--ok);font-weight:600}
.stats-view{padding:28px;overflow-y:auto;width:100%;background:var(--bg)}
.stats-view h2{margin-bottom:24px;color:var(--text);font-size:18px;font-weight:600;letter-spacing:0.3px}
.stat-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px;margin-bottom:28px}
.stat{background:var(--panel);border-radius:3px;padding:20px;border:1px solid var(--border);border-left:3px solid var(--accent);transition:transform 0.15s}
.stat:hover{transform:translateY(-2px)}
.stat.crit{border-left-color:var(--crit)}
.stat.warn{border-left-color:var(--warn)}
.stat.ok{border-left-color:var(--ok)}
.stat.caution{border-left-color:#ff9800}
.stat-label{font-size:11px;color:var(--text-secondary);margin-bottom:8px;text-transform:uppercase;letter-spacing:0.5px;font-weight:600}
.stat-val{font-size:32px;font-weight:700;color:var(--text)}
.chart-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(400px,1fr));gap:16px}
.chart{background:var(--panel);border-radius:3px;padding:20px;border:1px solid var(--border)}
.chart h3{font-size:13px;color:var(--text);margin-bottom:16px;font-weight:600}
.logs-view{padding:20px;display:flex;flex-direction:column;gap:16px;overflow-y:auto;width:100%;background:var(--bg)}
.filters{display:flex;gap:12px;flex-wrap:wrap;background:var(--panel);padding:16px;border-radius:3px;border:1px solid var(--border)}
.inp{flex:1;min-width:200px;padding:8px 12px;border:1px solid var(--border);border-radius:3px;font-size:12px;background:var(--input-bg);color:var(--text);transition:border-color 0.15s}
.inp:focus{outline:none;border-color:var(--accent)}
.sel{padding:8px 12px;border:1px solid var(--border);border-radius:3px;font-size:12px;background:var(--input-bg);color:var(--text);cursor:pointer}
.sel:focus{outline:none;border-color:var(--accent)}
.btn-sm{padding:8px 14px;font-size:12px}
table{width:100%;border-collapse:collapse;background:var(--panel);border-radius:3px;overflow:hidden;border:1px solid var(--border)}
th,td{padding:12px 16px;text-align:left;border-bottom:1px solid var(--border);font-size:12px}
th{background:var(--bg-tertiary);font-weight:600;cursor:pointer;user-select:none;color:var(--text-secondary);text-transform:uppercase;font-size:11px;letter-spacing:0.5px}
th:hover{background:var(--input-bg)}
tr:hover{background:var(--bg-tertiary)}
.badge{display:inline-block;padding:4px 9px;border-radius:3px;font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:0.3px}
.badge.crit{background:var(--crit);color:#000}
.badge.warn{background:var(--warn);color:#000}
.badge.info{background:var(--info);color:#000}
.badge.caution{background:#ff9800;color:#000}
.status{
  position:absolute;
  bottom:0;
  left:0;
  right:360px;
  background:var(--bg-secondary);
  border-top:1px solid var(--border);
  padding:0 20px;
  display:flex;
  align-items:center;
  gap:20px;
  font-size:11px;
  height:31px;
  color:var(--text-secondary);
  z-index:1001;
}
.stats-bar{
  position:absolute;
  bottom:31px;
  left:0;
  right:360px;
  background:var(--bg-secondary);
  border-top:1px solid var(--border);
  padding:12px 20px;
  display:flex;
  align-items:center;
  gap:16px;
  font-size:11px;
  height:60px;
  z-index:1000;
  overflow-x:auto;
}
.stat-mini{
  display:flex;
  align-items:center;
  gap:8px;
  padding:8px 14px;
  background:var(--bg-tertiary);
  border-radius:3px;
  border-left:3px solid var(--accent);
  min-width:100px;
  transition:transform 0.15s;
}
.stat-mini:hover{
  transform:translateY(-2px);
}
.stat-mini.crit{border-left-color:var(--crit);}
.stat-mini.warn{border-left-color:var(--warn);}
.stat-mini.ok{border-left-color:var(--ok);}
.stat-mini-val{
  font-size:24px;
  font-weight:700;
  color:var(--text);
  line-height:1;
}
.stat-mini-label{
  font-size:9px;
  color:var(--text-secondary);
  text-transform:uppercase;
  letter-spacing:0.5px;
  font-weight:600;
}
.dot{width:8px;height:8px;border-radius:50%;background:var(--ok);animation:dot 2s infinite}
@keyframes dot{0%,100%{opacity:1}50%{opacity:0.4}}
.dot.err{background:var(--crit)}
.modal{display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.75);align-items:center;justify-content:center;z-index:999;backdrop-filter:blur(4px)}
.modal.on{display:flex}
.mbox{background:var(--panel);padding:28px;border-radius:4px;width:420px;border:1px solid var(--border);box-shadow:0 8px 32px rgba(0,0,0,0.6)}
.mbox h3{margin-bottom:20px;font-size:16px;font-weight:600;color:var(--text)}
.fg{margin-bottom:16px}
.fg label{display:block;margin-bottom:6px;font-size:12px;font-weight:500;color:var(--text-secondary);text-transform:uppercase;letter-spacing:0.3px}
.fg input,.fg select{width:100%;padding:10px 12px;border:1px solid var(--border);border-radius:3px;font-size:13px;background:var(--input-bg);color:var(--text);transition:border-color 0.15s}
.fg input:focus,.fg select:focus{outline:none;border-color:var(--accent)}
.mact{display:flex;gap:12px;margin-top:20px}
.pulse{width:12px;height:12px;border-radius:50%;position:absolute;animation:pul 2s infinite}
@keyframes pul{0%{transform:scale(1);opacity:0.6}70%{transform:scale(2.5);opacity:0}100%{opacity:0}}
.pulse.r{background:rgba(244,135,113,0.6)}
.pulse.b{background:rgba(0,122,204,0.6)}
.pulse.o{background:rgba(204,167,0,0.6)}
.flash{position:fixed;top:0;left:0;width:100%;height:100%;background:var(--crit);opacity:0;pointer-events:none;z-index:998}
.flash.on{animation:fla 0.4s 3}
@keyframes fla{0%,100%{opacity:0}50%{opacity:0.15}}
.chk{margin-right:6px;cursor:pointer}
::-webkit-scrollbar{width:10px;height:10px}
::-webkit-scrollbar-track{background:var(--bg)}
::-webkit-scrollbar-thumb{background:var(--border);border-radius:5px}
::-webkit-scrollbar-thumb:hover{background:var(--text-secondary)}
@keyframes subGlow{0%,100%{opacity:0.4;transform:scale(1)}50%{opacity:0.8;transform:scale(1.2)}}
.loading-screen{
  position:fixed;
  top:0;
  left:0;
  width:100%;
  height:100%;
  background:var(--bg);
  display:flex;
  flex-direction:column;
  align-items:center;
  justify-content:center;
  z-index:9999;
  transition:opacity 0.5s ease;
}
.loading-screen.hide{
  opacity:0;
  pointer-events:none;
}
.loader{
  width:60px;
  height:60px;
  border:4px solid var(--border);
  border-top-color:var(--accent);
  border-radius:50%;
  animation:spin 1s linear infinite;
}
@keyframes spin{
  to{transform:rotate(360deg)}
}
.loading-text{
  margin-top:20px;
  font-size:14px;
  color:var(--text-secondary);
  font-weight:500;
}
.loading-subtext{
  margin-top:8px;
  font-size:11px;
  color:var(--text-secondary);
  opacity:0.6;
}
</style>
</head><body>
<div class="loading-screen" id="loading">
  <div style="text-align:center">
    <div style="font-size:48px;margin-bottom:20px">⚡</div>
    <div class="loader"></div>
    <div class="loading-text">Initializing Overwatch SCADA</div>
    <div class="loading-subtext" id="load-status">Starting up...</div>
  </div>
</div>

<div class="flash" id="flash"></div>

<div class="top">
  <div class="top-title">⚡ Overwatch SCADA - Region 5 Bicol</div>
  <div class="top-btn" onclick="exp()">📥 Export</div>
  <div class="top-btn" onclick="ref()">🔄 Refresh</div>
  <div class="top-btn" onclick="dark()">🌙 Darker</div>
</div>

<div class="tabs">
  <div class="tab on" onclick="sw('map')">🗺️ Map</div>
  <div class="tab" onclick="sw('stats')">📊 Stats</div>
  <div class="tab" onclick="sw('logs')">📋 Logs</div>
</div>

<div class="main">
  <div class="content on" id="map-content">
    <div class="map-view">
      <div id="map"></div>
      
      <div class="map-ctrl">
        <div class="map-ctrl-title">🗺️ MAP LAYERS</div>
        <div class="map-ctrl-opt on" onclick="chgMap('osm')">
          <input type="radio" name="maptype" class="chk" checked>Standard
        </div>
        <div class="map-ctrl-opt" onclick="chgMap('satellite')">
          <input type="radio" name="maptype" class="chk">Satellite
        </div>
        <div class="map-ctrl-opt" onclick="chgMap('terrain')">
          <input type="radio" name="maptype" class="chk">Terrain
        </div>
        <div class="map-ctrl-opt" onclick="chgMap('dark')">
          <input type="radio" name="maptype" class="chk">Dark Mode
        </div>
        <div class="map-ctrl-title">⚡ OVERLAYS</div>
        <div class="map-ctrl-opt" onclick="togOverlay('transmission')">
          <input type="checkbox" id="chk-trans" class="chk">Transmission Lines
        </div>
        <div class="map-ctrl-opt" onclick="togOverlay('substations')">
          <input type="checkbox" id="chk-subs" class="chk">Substations
        </div>
        <div class="map-ctrl-opt" onclick="togOverlay('coverage')">
          <input type="checkbox" id="chk-cov" class="chk">Service Areas
        </div>
      </div>
      
      <div class="side">
  <div>
    <h3>ℹ️ About</h3>
    <div class="box" style="font-size:11px;line-height:1.8">
      <strong style="display:block;margin-bottom:8px;font-size:12px;color:var(--accent)">Overwatch SCADA</strong>
      <div style="color:var(--text-secondary);margin-bottom:12px">
        Real-time monitoring system for electrical fault detection and management in Region 5 Bicol.
      </div>
      <div style="border-top:1px solid var(--border);padding-top:12px;margin-top:12px">
        <strong style="font-size:10px;color:var(--text-secondary);text-transform:uppercase;letter-spacing:0.5px">Developed By:</strong>
        <div style="margin-top:6px;color:var(--text)">
          • Mark Joseph Delas Llagas<br>
          • Jureen Dominique Sese<br>
          • Justin Valenzuela
        </div>
        <div style="margin-top:8px;font-size:10px;color:var(--text-secondary)">
          BS Electrical Engineering<br>
          Bicol University College of Engineering
        </div>
      </div>
    </div>
  </div>

  <div>
    <h3>📖 Quick Guide</h3>
    <div class="box" style="font-size:11px;line-height:1.7">
      <div style="margin-bottom:10px">
        <strong style="color:var(--accent)">🗺️ Map View</strong>
        <div style="color:var(--text-secondary);margin-top:4px">
          • Click markers to view fault details<br>
          • Use map controls to change layers<br>
          • Toggle transmission lines & substations
        </div>
      </div>
      <div style="margin-bottom:10px;padding-top:10px;border-top:1px solid var(--border)">
        <strong style="color:var(--accent)">✔ Acknowledgement</strong>
        <div style="color:var(--text-secondary);margin-top:4px">
          • Click "Acknowledge" button<br>
          • Enter Report ID and your name<br>
          • Select status and submit
        </div>
      </div>
      <div style="margin-bottom:10px;padding-top:10px;border-top:1px solid var(--border)">
        <strong style="color:var(--accent)">📊 Statistics</strong>
        <div style="color:var(--text-secondary);margin-top:4px">
          • View fault trends and metrics<br>
          • Analyze by severity and device<br>
          • Track resolution rates
        </div>
      </div>
      <div style="padding-top:10px;border-top:1px solid var(--border)">
        <strong style="color:var(--accent)">🔍 Logs</strong>
        <div style="color:var(--text-secondary);margin-top:4px">
          • Search and filter fault records<br>
          • Sort by any column<br>
          • Export data to CSV
        </div>
      </div>
    </div>
  </div>

  <div>
    <h3>📍 Latest Fault</h3>
    <div class="box" id="latest">Loading...</div>
  </div>

  <div>
    <h3>🎮 Actions</h3>
    <button class="btn tog" id="monitor" onclick="togMon()">📍 Monitor: OFF</button>
    <button class="btn btn-1" onclick="ref()">🔄 Refresh</button>
    <button class="btn btn-ok" onclick="showAck()">✔ Acknowledge</button>
    <button class="btn btn-2" onclick="zAll()">🎯 View All</button>
  </div>

  <div>
    <h3>🔔 Alerts</h3>
    <button class="btn tog on" id="sound" onclick="togSnd()">🔊 Sound: ON</button>
  </div>
</div>

<!-- ADD THIS STATS BAR -->
      <div class="stats-bar" id="stats-bar">
        <div class="stat-mini">
          <div>
            <div class="stat-mini-val" id="stat-total">0</div>
            <div class="stat-mini-label">Total</div>
          </div>
        </div>
        <div class="stat-mini">
          <div>
            <div class="stat-mini-val" id="stat-today">0</div>
            <div class="stat-mini-label">Today</div>
          </div>
        </div>
        <div class="stat-mini">
          <div>
            <div class="stat-mini-val" id="stat-week">0</div>
            <div class="stat-mini-label">This Week</div>
          </div>
        </div>
        <div class="stat-mini ok">
          <div>
            <div class="stat-mini-val" id="stat-ack">0</div>
            <div class="stat-mini-label">Acknowledged</div>
          </div>
        </div>
        <div class="stat-mini crit">
          <div>
            <div class="stat-mini-val" id="stat-pend">0</div>
            <div class="stat-mini-label">Pending</div>
          </div>
        </div>
        <div class="stat-mini crit">
          <div>
            <div class="stat-mini-val" id="stat-crit">0</div>
            <div class="stat-mini-label">Critical</div>
          </div>
        </div>
        <div class="stat-mini warn">
          <div>
            <div class="stat-mini-val" id="stat-warn">0</div>
            <div class="stat-mini-label">Warning</div>
          </div>
        </div>
        <div class="stat-mini" style="border-left-color:#ff9800">  <!-- ADD THIS -->
  <div>
    <div class="stat-mini-val" id="stat-caution">0</div>
    <div class="stat-mini-label">Caution</div>
  </div>
</div>
        <div class="stat-mini">
          <div>
            <div class="stat-mini-val" id="stat-info">0</div>
            <div class="stat-mini-label">Info</div>
          </div>
        </div>
      </div>

      <div class="status">
        <div style="display:flex;align-items:center;gap:5px">
          <div class="dot" id="dot"></div><span id="conn">Connected</span>
        </div>
        <div>|</div>
        <div id="upd">Last: --:--:--</div>
        <div>|</div>
        <div id="cnt">Faults: 0</div>
        <div style="margin-left:auto">👤 Operator</div>
      </div>
    </div>
  </div>

  <div class="content" id="stats-content">
    <div class="stats-view">
      <h2 style="margin-bottom:20px;color:var(--accent)">📊 Statistics</h2>
      <div class="stat-grid" id="sgrid"></div>
      <div class="chart-grid">
        <div class="chart"><h3>Severity Distribution</h3><canvas id="c1"></canvas></div>
        <div class="chart"><h3>Faults by Device</h3><canvas id="c2"></canvas></div>
      </div>
    </div>
  </div>

  <div class="content" id="logs-content">
    <div class="logs-view">
      <div class="filters">
        <input class="inp" id="search" placeholder="🔍 Search..." oninput="filt()">
        <select class="sel" id="fdev" onchange="filt()"><option value="">All Devices</option></select>
        <select class="sel" id="fstat" onchange="filt()">
          <option value="">All Status</option><option value="p">Pending</option><option value="a">Acknowledged</option>
        </select>
        <select class="sel" id="fsev" onchange="filt()">
          <option value="">All Severity</option>
          <option value="CRITICAL">Critical</option>
          <option value="WARNING">Warning</option>
          <option value="CAUTION">Caution</option>  <!-- ADD THIS -->
          <option value="INFO">Info</option>
        </select>
        <button class="btn btn-2 btn-sm" onclick="clr()">🗑️ Clear</button>
      </div>
      <div style="overflow-x:auto">
        <table><thead><tr>
          <th onclick="sort(0)">ID ⇅</th><th onclick="sort(1)">Date ⇅</th><th onclick="sort(2)">Time ⇅</th>
          <th onclick="sort(3)">Device ⇅</th><th onclick="sort(4)">Dist ⇅</th><th onclick="sort(5)">Severity ⇅</th>
          <th onclick="sort(6)">Status ⇅</th><th onclick="sort(7)">Modified ⇅</th><th>Act</th>
        </tr></thead><tbody id="tbody"></tbody></table>
      </div>
    </div>
  </div>
</div>

<div id="modal" class="modal">
  <div class="mbox">
    <h3>✔ Acknowledge Fault</h3>
    <div class="fg"><label>Report ID</label><input id="aid" placeholder="Enter ID"></div>
    <div class="fg"><label>Status</label>
      <select id="astat">
        <option>Acknowledged</option><option>Resolved</option>
        <option>Under Investigation</option><option>Fixed</option>
      </select>
    </div>
    <div class="fg"><label>Your Name</label><input id="aname" placeholder="Enter name"></div>
    <div class="mact">
      <button class="btn btn-2" style="flex:1" onclick="hideAck()">Cancel</button>
      <button class="btn btn-ok" style="flex:1" onclick="subAck()">Submit</button>
    </div>
  </div>
</div>

<script>
let map,data=[],circ=[],mon=false,snd=true,last=null,charts={},sdir={};
let currentLayer,transmissionLayer,substationLayer,coverageLayer;

const TRANSMISSION_LINES = [
  {from:[13.621775,123.194824],to:[13.148300,123.712400],voltage:230,name:'Naga-Daraga 230kV'},
  {from:[13.148300,123.712400],to:[14.112200,122.955300],voltage:230,name:'Daraga-Sorsogon 230kV'},
  {from:[13.621775,123.194824],to:[14.099578,122.955035],voltage:69,name:'Naga-Daet (via Camarines Norte) 69kV'},
  {from:[13.148300,123.712400],to:[13.1442028,123.7447158],voltage:69,name:'Daraga-Legazpi 69kV'},
  {from:[13.148300,123.712400],to:[13.432400,123.411500],voltage:69,name:'Daraga-Iriga 69kV'},
  {from:[14.112200,122.955300],to:[12.667904,123.8736101],voltage:69,name:'Sorsogon/Daet-Bulan 69kV'},
  {from:[13.621775,123.194824],to:[13.554725,123.274724],voltage:69,name:'Naga-Pili 69kV'},
  {from:[13.148300,123.712400],to:[13.595469,123.281256],voltage:69,name:'Daraga-Santo Domingo / Pili area 69kV'},
  {from:[13.621775,123.194824],to:[13.405867,123.4059345],voltage:34.5,name:'Naga Distribution (approx to Iriga area)'},
  {from:[13.1442028,123.7447158],to:[13.420537,123.418047],voltage:34.5,name:'Legazpi Distribution (approx)'}
];

const SUBSTATIONS = [
  {name:'Naga Substation (city center proxy)',lat:13.621775,lng:123.194824,voltage:230,type:'Transmission'},
  {name:'Daraga Substation (town center proxy)',lat:13.148300,lng:123.712400,voltage:230,type:'Transmission'},
  {name:'Sorsogon / Daet Substation (regional proxy)',lat:12.992710,lng:124.014746,voltage:230,type:'Transmission'},
  {name:'Legazpi Substation (city center / SM Legazpi)',lat:13.144203,lng:123.744716,voltage:69,type:'Distribution'},
  {name:'Iriga Substation (city center proxy)',lat:13.432400,lng:123.411500,voltage:69,type:'Distribution'},
  {name:'Daet Substation (CANORECO / Daet center)',lat:14.112200,lng:122.955300,voltage:69,type:'Distribution'},
  {name:'Pili Substation (Pili town center proxy)',lat:13.554725,lng:123.274724,voltage:69,type:'Distribution'},
  {name:'Bulan Substation (Bulan town center proxy)',lat:12.667904,lng:123.873610,voltage:69,type:'Distribution'}
];

const COVERAGE_AREAS = [
  {name:'CASURECO II (Naga)',center:[13.621775,123.194824],radius:25000,color:'#ff6b6b'},
  {name:'ALECO (Legazpi)',center:[13.144203,123.744716],radius:30000,color:'#4ecdc4'},
  {name:'SORECO II (Sorsogon)',center:[12.992710,124.014746],radius:28000,color:'#45b7d1'},
  {name:'CASURECO I (Libmanan)',center:[13.695335,123.061928],radius:22000,color:'#96ceb4'},
  {name:'CANORECO (Daet)',center:[14.112200,122.955300],radius:20000,color:'#ffeaa7'}
];


function init(){
  try{
    updateLoadStatus('Initializing map...');
    
    map=L.map('map').setView([13.41,123.35],9);
    currentLayer=L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{
      attribution:'© OpenStreetMap'
    }).addTo(map);
    
    transmissionLayer=L.layerGroup();
    substationLayer=L.layerGroup();
    coverageLayer=L.layerGroup();
    
    updateLoadStatus('Loading power infrastructure...');
    
    // Try OSM first, fall back to manual data if it fails
    fetchOSMPowerLines();
    
    drawSubstations();
    drawCoverageAreas();
    
    updateLoadStatus('Fetching fault data...');
    
    // Initial fetch with loading screen
    ref().then(()=>{
      updateLoadStatus('Ready!');
      setTimeout(hideLoading, 500);
    });
    
    // Set up refresh interval
    setInterval(ref, 3000);
    
  }catch(e){
    console.error('Init error:',e);
    updateLoadStatus('Error: ' + e.message);
    setTimeout(hideLoading, 2000);
  }
}

function drawTransmissionLines(){
  TRANSMISSION_LINES.forEach(line=>{
    const color=line.voltage===230?'#e74c3c':line.voltage===69?'#3498db':'#2ecc71';
    const weight=line.voltage===230?4:line.voltage===69?3:2;
    const opacity=line.voltage===230?0.8:0.6;
    const polyline=L.polyline([line.from,line.to],{
      color:color,weight:weight,opacity:opacity,
      dashArray:line.voltage===34.5?'5,10':null
    });
    polyline.bindPopup('<b>'+line.name+'</b><br>Voltage: '+line.voltage+' kV<br>'+
      'Type: '+(line.voltage>=230?'Transmission':line.voltage>=69?'Sub-transmission':'Distribution'));
    transmissionLayer.addLayer(polyline);
  });
}

function drawSubstations(){
  SUBSTATIONS.forEach(sub=>{
    const isTransmission = sub.voltage >= 230;
    const color = isTransmission ? '#f48771' : '#4fc1ff';
    const bgColor = isTransmission ? 'rgba(244,135,113,0.2)' : 'rgba(79,193,255,0.2)';
    
    const icon = L.divIcon({
      html: `
        <div style="position:relative;text-align:center;">
          <!-- Outer glow -->
          <div style="
            position:absolute;
            width:32px;
            height:32px;
            top:-8px;
            left:-8px;
            border-radius:50%;
            background:${bgColor};
            animation:subGlow 2s ease-in-out infinite;
          "></div>
          <!-- Main icon -->
          <div style="
            position:relative;
            width:20px;
            height:20px;
            background:${color};
            border:2px solid #fff;
            border-radius:4px;
            box-shadow:0 3px 10px rgba(0,0,0,0.5);
            display:flex;
            align-items:center;
            justify-content:center;
            font-weight:bold;
            font-size:10px;
            color:#000;
          ">⚡</div>
          <!-- Label -->
          <div style="
            position:absolute;
            top:24px;
            left:50%;
            transform:translateX(-50%);
            background:rgba(37,37,38,0.95);
            color:#ccc;
            padding:4px 9px;
            border-radius:3px;
            font-size:10px;
            white-space:nowrap;
            border:1px solid #3e3e42;
            font-weight:600;
            box-shadow:0 2px 6px rgba(0,0,0,0.4);
          ">${sub.name.replace(' Substation','')}<br/>
          <span style="font-size:9px;color:#858585;">${sub.voltage}kV</span>
          </div>
        </div>
      `,
      className:'',
      iconSize:[20,60],
      iconAnchor:[10,10]
    });
    
    const marker = L.marker([sub.lat,sub.lng],{icon:icon});
    
    marker.bindPopup(`
      <div style="font-family:'Segoe UI',sans-serif;min-width:200px;">
        <div style="
          font-weight:600;
          font-size:14px;
          margin-bottom:10px;
          color:#007acc;
          padding-bottom:8px;
          border-bottom:1px solid #3e3e42;
        ">
          ${sub.name}
        </div>
        <table style="width:100%;font-size:11px;line-height:1.8;">
          <tr>
            <td style="color:#858585;font-weight:500;">Voltage:</td>
            <td style="color:#ccc;text-align:right;font-weight:600;">${sub.voltage} kV</td>
          </tr>
          <tr>
            <td style="color:#858585;font-weight:500;">Type:</td>
            <td style="color:#ccc;text-align:right;">${sub.type}</td>
          </tr>
          <tr>
            <td style="color:#858585;font-weight:500;">Latitude:</td>
            <td style="color:#ccc;text-align:right;font-family:monospace;">${sub.lat.toFixed(5)}</td>
          </tr>
          <tr>
            <td style="color:#858585;font-weight:500;">Longitude:</td>
            <td style="color:#ccc;text-align:right;font-family:monospace;">${sub.lng.toFixed(5)}</td>
          </tr>
        </table>
      </div>
    `);
    
    substationLayer.addLayer(marker);
  });
}

function drawCoverageAreas(){
  COVERAGE_AREAS.forEach(area=>{
    const circle=L.circle(area.center,{
      radius:area.radius,color:area.color,fillColor:area.color,
      fillOpacity:0.1,opacity:0.4,weight:2,dashArray:'5,10'
    });
    circle.bindPopup('<b>'+area.name+'</b><br>Service Coverage Area');
    coverageLayer.addLayer(circle);
  });
}

function chgMap(type){
  try{
    map.removeLayer(currentLayer);
    switch(type){
      case 'satellite':
        currentLayer=L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',{attribution:'© Esri'});
        break;
      case 'terrain':
        currentLayer=L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',{attribution:'© OpenTopoMap'});
        break;
      case 'dark':
        currentLayer=L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',{attribution:'© CartoDB'});
        break;
      default:
        currentLayer=L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'© OpenStreetMap'});
    }
    currentLayer.addTo(map);
    document.querySelectorAll('.map-ctrl-opt').forEach((el,i)=>{
      if(i<4){el.classList.remove('on');el.querySelector('input').checked=false;}
    });
    event.target.closest('.map-ctrl-opt').classList.add('on');
    event.target.closest('.map-ctrl-opt').querySelector('input').checked=true;
  }catch(e){console.error('Map change error:',e);}
}

function togOverlay(type){
  try{
    const checkbox=document.getElementById('chk-'+type.substring(0,type==='transmission'?5:type==='substations'?4:3));
    switch(type){
      case 'transmission':
        if(map.hasLayer(transmissionLayer)){map.removeLayer(transmissionLayer);checkbox.checked=false;}
        else{map.addLayer(transmissionLayer);checkbox.checked=true;}
        break;
      case 'substations':
        if(map.hasLayer(substationLayer)){map.removeLayer(substationLayer);checkbox.checked=false;}
        else{map.addLayer(substationLayer);checkbox.checked=true;}
        break;
      case 'coverage':
        if(map.hasLayer(coverageLayer)){map.removeLayer(coverageLayer);checkbox.checked=false;}
        else{map.addLayer(coverageLayer);checkbox.checked=true;}
        break;
    }
  }catch(e){console.error('Overlay toggle error:',e);}
}

async function ref(){
  try{
    const d = await window.pywebview.api.get_faults();
    if(!d||!d.length)return;
    data = d;
    const l = d[d.length-1];
    
    // Check if this is a NEW fault
    const isNewFault = last !== null && l.id !== last;
    
    // Sound/Flash alert for NEW faults only
    if(snd && isNewFault){
      console.log('🔊 Playing sound for:', l.sev, 'Fault ID:', l.id);
      beep(l.sev);
      flash();
    }
    
    // Monitor mode: continuously track critical/warning faults
    if(mon && (l.sev==='CRITICAL' || l.sev==='WARNING')){
      console.log('🎯 Monitoring fault:', l.id);
      map.setView([l.lat,l.lng],14);
    }
    
    last = l.id;
    upLat(l);
    upMap(d);
    upTab(d);
    upDev(d);
    upBar(d);
    upStatsBar(d);
  }catch(e){
    console.error('Refresh error:',e);
  }
}
function upLat(f){
  try{
    const s=f.ack?'✓ Ack':'⚠ Pending';
    document.getElementById('latest').innerHTML='<strong>'+f.id+'</strong> '+s+'<br>Device: '+f.device+
      '<br>Dist: '+f.dist+' m<br>Sev: '+f.sev+'<br>Time: '+f.date+' '+f.time;
  }catch(e){console.error('Update latest error:',e);}
}

function upMap(d){
  try{
    // Clear all previous layers (circles AND markers)
    circ.forEach(layer => map.removeLayer(layer));
    circ = [];

    d.forEach(f => {
      const col = f.ack ? '#0078d4' : f.sev === 'CRITICAL' ? '#dc3545' : f.sev === 'WARNING' ? '#ffc107' : '#17a2b8';
      
      // 1. Create the circle
      const c = L.circle([f.lat, f.lng], {
        color: col,
        fillColor: col,
        fillOpacity: 0.2,
        radius: f.dist
      }).addTo(map);

      // 2. Create the pulsing icon marker
      const pc = f.ack ? 'b' : f.sev === 'CRITICAL' ? 'r' : 'o';
      const ic = L.divIcon({
        html: '<div class="pulse ' + pc + '"></div>',
        className: '',
        iconSize: [12, 12]
      });
      const marker = L.marker([f.lat, f.lng], {icon: ic}).addTo(map);

      // 3. Create the new popup content with a button
      // We use CSS variables to match your dark/light theme
      const popupBtnStyle = `
        padding: 6px 12px;
        background: var(--accent);
        color: #fff;
        border: none;
        border-radius: 4px;
        cursor: pointer;
        font-weight: 600;
        font-family: 'Segoe UI', sans-serif;
        margin-top: 10px;
        width: 100%;
        transition: background 0.15s ease;
      `;
      
      const popupContent = `
        <div style="font-family: 'Segoe UI', sans-serif; font-size: 13px; line-height: 1.6; color: var(--text);">
          <b style="font-size: 14px; color: var(--accent);">${f.id}</b><br>
          <b>Device:</b> ${f.device}<br>
          <b>Dist:</b> ${f.dist} m<br>
          <b>Severity:</b> ${f.sev}<br>
          <b>Status:</b> ${f.ack ? ('✓ ' + f.status) : '⚠ Pending'}<br>
          <button style="${popupBtnStyle}" 
                  onmouseover="this.style.background='var(--accent-hover)'"
                  onmouseout="this.style.background='var(--accent)'"
                  onclick="clickAck('${f.id}')">
            ✔ Acknowledge
          </button>
        </div>
      `;

      // 4. Bind popup to both circle and marker
      c.bindPopup(popupContent);
      marker.bindPopup(popupContent);

      // 5. Add both layers to the circ array to be cleared on next refresh
      circ.push(c);
      circ.push(marker);
    });
  } catch(e) {
    console.error('Map update error:', e);
  }
}

function upTab(d){
  try{
    const tb=document.getElementById('tbody');tb.innerHTML='';
    d.slice(-50).reverse().forEach(f=>{
      const r=tb.insertRow();
      r.innerHTML='<td>'+f.id+'</td><td>'+f.date+'</td><td>'+f.time+'</td><td>'+f.device+
        '</td><td>'+f.dist+'</td><td><span class="badge '+f.sev.toLowerCase()+'">'+f.sev+'</span></td>'+
        '<td>'+(f.ack?'✓ '+f.status:'⚠ Pending')+'</td><td>'+(f.mod||'-')+'</td>'+
        '<td><button class="btn btn-sm btn-1" onclick="zm('+f.lat+','+f.lng+')" style="padding:4px 8px">🔍</button></td>';
    });
  }catch(e){console.error('Table update error:',e);}
}

function upDev(d){
  try{
    const s=document.getElementById('fdev');
    const devs=[...new Set(d.map(f=>f.device))];
    s.innerHTML='<option value="">All Devices</option>';
    devs.forEach(dv=>s.innerHTML+='<option>'+dv+'</option>');
  }catch(e){console.error('Device update error:',e);}
}

function upBar(d){
  try{
    document.getElementById('dot').classList.remove('err');
    document.getElementById('conn').textContent='Connected';
    document.getElementById('cnt').textContent='Faults: '+d.length;
    document.getElementById('upd').textContent='Last: '+new Date().toLocaleTimeString();
  }catch(e){console.error('Status bar error:',e);}
}

function upStatsBar(d) {
  try {
    const today = new Date().toISOString().split('T')[0];
    const weekAgo = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];
    
    const stats = {
      total: d.length,
      today: d.filter(f => f.date === today).length,
      week: d.filter(f => f.date >= weekAgo).length,
      ack: d.filter(f => f.ack).length,
      pend: d.filter(f => !f.ack).length,
      crit: d.filter(f => f.sev === 'CRITICAL').length,
      warn: d.filter(f => f.sev === 'WARNING').length,
      caution: d.filter(f => f.sev === 'CAUTION').length,  // ← ADD THIS
      info: d.filter(f => f.sev === 'INFO').length
    };
    
    document.getElementById('stat-total').textContent = stats.total;
    document.getElementById('stat-today').textContent = stats.today;
    document.getElementById('stat-week').textContent = stats.week;
    document.getElementById('stat-ack').textContent = stats.ack;
    document.getElementById('stat-pend').textContent = stats.pend;
    document.getElementById('stat-crit').textContent = stats.crit;
    document.getElementById('stat-warn').textContent = stats.warn;
    document.getElementById('stat-caution').textContent = stats.caution;  // ← ADD THIS
    document.getElementById('stat-info').textContent = stats.info;
  } catch(e) {
    console.error('Stats bar update error:', e);
  }
}

async function ldStats(){
  try{
    const s=await window.pywebview.api.get_stats();
    document.getElementById('sgrid').innerHTML=
      '<div class="stat"><div class="stat-label">Total</div><div class="stat-val">'+s.total+'</div></div>'+
      '<div class="stat"><div class="stat-label">Today</div><div class="stat-val">'+s.today+'</div></div>'+
      '<div class="stat"><div class="stat-label">This Week</div><div class="stat-val">'+s.week+'</div></div>'+
      '<div class="stat ok"><div class="stat-label">Acknowledged</div><div class="stat-val">'+s.ack+'</div></div>'+
      '<div class="stat crit"><div class="stat-label">Pending</div><div class="stat-val">'+s.pend+'</div></div>'+
      '<div class="stat crit"><div class="stat-label">Critical</div><div class="stat-val">'+s.crit+'</div></div>'+
      '<div class="stat warn"><div class="stat-label">Warning</div><div class="stat-val">'+s.warn+'</div></div>'+
      '<div class="stat" style="border-left-color:#ff9800"><div class="stat-label">Caution</div><div class="stat-val">'+s.caution+'</div></div>'+ 
      '<div class="stat"><div class="stat-label">Info</div><div class="stat-val">'+s.info+'</div></div>';
    
    if(charts.c1)charts.c1.destroy();
    charts.c1=new Chart(document.getElementById('c1'),{
      type:'doughnut',
      data:{labels:['Critical','Warning','Caution','Info'],datasets:[{data:[s.crit,s.warn,s.caution,s.info],
        backgroundColor:['#dc3545','#ffc107','#ff9800','#17a2b8']}]},  // ← UPDATE THIS
      options:{responsive:true,plugins:{legend:{position:'bottom'}}}
    });
    
    if(charts.c2)charts.c2.destroy();
    charts.c2=new Chart(document.getElementById('c2'),{
      type:'bar',
      data:{labels:Object.keys(s.devs),datasets:[{label:'Faults',data:Object.values(s.devs),
        backgroundColor:'#0078d4'}]},
      options:{responsive:true,plugins:{legend:{display:false}},scales:{y:{beginAtZero:true}}}
    });
  }catch(e){console.error('Stats load error:',e);}
}

function sw(t){
  try{
    document.querySelectorAll('.tab').forEach(x=>x.classList.remove('on'));
    event.target.classList.add('on');
    document.querySelectorAll('.content').forEach(x=>x.classList.remove('on'));
    document.getElementById(t+'-content').classList.add('on');
    if(t==='stats')ldStats();
  }catch(e){console.error('Tab switch error:',e);}
}

function filt(){
  try{
    const q=document.getElementById('search').value.toLowerCase();
    const dv=document.getElementById('fdev').value;
    const st=document.getElementById('fstat').value;
    const sv=document.getElementById('fsev').value;
    document.querySelectorAll('#tbody tr').forEach(r=>{
      const c=r.cells;
      const mq=c[0].textContent.toLowerCase().includes(q)||c[3].textContent.toLowerCase().includes(q);
      const md=!dv||c[3].textContent===dv;
      const ms=!st||(st==='p'&&c[6].textContent.includes('Pending'))||(st==='a'&&!c[6].textContent.includes('Pending'));
      const mv=!sv||c[5].textContent.includes(sv);
      r.style.display=(mq&&md&&ms&&mv)?'':'none';
    });
  }catch(e){console.error('Filter error:',e);}
}

function sort(i){
  try{
    const tb=document.getElementById('tbody');
    const rs=Array.from(tb.rows);
    const d=sdir[i]==='a'?'d':'a';sdir[i]=d;
    rs.sort((a,b)=>{
      const av=a.cells[i].textContent.trim(),bv=b.cells[i].textContent.trim();
      const an=parseFloat(av),bn=parseFloat(bv);
      if(!isNaN(an)&&!isNaN(bn))return d==='a'?an-bn:bn-an;
      return d==='a'?av.localeCompare(bv):bv.localeCompare(av);
    });
    rs.forEach(r=>tb.appendChild(r));
  }catch(e){console.error('Sort error:',e);}
}

function clr(){
  try{
    document.getElementById('search').value='';
    document.getElementById('fdev').value='';
    document.getElementById('fstat').value='';
    document.getElementById('fsev').value='';
    filt();
  }catch(e){console.error('Clear error:',e);}
}

function togMon(){
  try{
    mon=!mon;
    const b=document.getElementById('monitor');
    b.classList.toggle('on',mon);
    b.textContent=mon?'🎯 Monitor: ON':'📍 Monitor: OFF';
  }catch(e){console.error('Toggle monitor error:',e);}
}

function togSnd(){
  try{
    snd=!snd;
    const b=document.getElementById('sound');
    b.classList.toggle('on',snd);
    b.textContent=snd?'🔊 Sound: ON':'🔇 Sound: OFF';
  }catch(e){console.error('Toggle sound error:',e);}
}

function dark(){
  try{
    document.documentElement.toggleAttribute('dark');
  }catch(e){console.error('Dark mode error:',e);}
}

function zm(la,ln){
  try{
    sw('map');
    setTimeout(()=>map.setView([la,ln],15),100);
  }catch(e){console.error('Zoom error:',e);}
}

function zAll(){
  try{
    if(!data.length)return;
    map.fitBounds(L.latLngBounds(data.map(f=>[f.lat,f.lng])),{padding:[50,50]});
  }catch(e){console.error('Zoom all error:',e);}
}

function beep(s){
  try{
    const ctx=new(window.AudioContext||window.webkitAudioContext)();
    
    if(s==='CRITICAL'){
      // CRITICAL: Alarming siren-like sound (two-tone alternating)
      const playTone=(freq,start,dur)=>{
        const osc=ctx.createOscillator(),gain=ctx.createGain();
        osc.connect(gain);gain.connect(ctx.destination);
        osc.frequency.value=freq;
        osc.type='sawtooth';  // Harsher sound
        gain.gain.setValueAtTime(0.4,start);
        gain.gain.exponentialRampToValueAtTime(0.01,start+dur);
        osc.start(start);osc.stop(start+dur);
      };
      
      // Three cycles of alternating high-low siren
      for(let i=0;i<3;i++){
        playTone(800,ctx.currentTime+i*0.4,0.2);      // High tone
        playTone(600,ctx.currentTime+i*0.4+0.2,0.2);  // Low tone
      }
      
    }else if(s==='WARNING'){
      // WARNING: Urgent beep-beep-beep (triple beep)
      const playBeep=(start)=>{
        const osc=ctx.createOscillator(),gain=ctx.createGain();
        osc.connect(gain);gain.connect(ctx.destination);
        osc.frequency.value=700;
        osc.type='square';
        gain.gain.setValueAtTime(0.3,start);
        gain.gain.exponentialRampToValueAtTime(0.01,start+0.15);
        osc.start(start);osc.stop(start+0.15);
      };
      
      playBeep(ctx.currentTime);
      playBeep(ctx.currentTime+0.2);
      playBeep(ctx.currentTime+0.4);
      
    }else if(s==='CAUTION'){
      // CAUTION: Double beep
      const playBeep=(start)=>{
        const osc=ctx.createOscillator(),gain=ctx.createGain();
        osc.connect(gain);gain.connect(ctx.destination);
        osc.frequency.value=600;
        gain.gain.setValueAtTime(0.25,start);
        gain.gain.exponentialRampToValueAtTime(0.01,start+0.2);
        osc.start(start);osc.stop(start+0.2);
      };
      
      playBeep(ctx.currentTime);
      playBeep(ctx.currentTime+0.3);
      
    }else{
      // INFO: Single soft beep
      const osc=ctx.createOscillator(),gain=ctx.createGain();
      osc.connect(gain);gain.connect(ctx.destination);
      osc.frequency.value=500;
      gain.gain.setValueAtTime(0.2,ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01,ctx.currentTime+0.3);
      osc.start();osc.stop(ctx.currentTime+0.3);
    }
  }catch(e){console.error('Beep error:',e);}
}

function flash(){
  try{
    document.getElementById('flash').classList.add('on');
    setTimeout(()=>document.getElementById('flash').classList.remove('on'),1200);
  }catch(e){console.error('Flash error:',e);}
}

function clickAck(id) {
  try {
    // Pre-fill the Report ID input field
    document.getElementById('aid').value = id;
    // Show the modal
    showAck();
  } catch(e) {
    console.error('Click ack error:', e);
  }
}
function showAck(){
  try{
    document.getElementById('modal').classList.add('on');
  }catch(e){console.error('Show ack error:',e);}
}

function hideAck(){
  try{
    document.getElementById('modal').classList.remove('on');
  }catch(e){console.error('Hide ack error:',e);}
}

async function subAck(){
  try{
    const id=document.getElementById('aid').value.trim();
    const st=document.getElementById('astat').value;
    const nm=document.getElementById('aname').value.trim();
    if(!id||!nm){alert('Fill all fields');return;}
    const r=await window.pywebview.api.ack_fault(id,st,nm);
    if(r.ok){alert('✓ Acknowledged!');hideAck();ref();}
    else alert('Error: '+r.err);
  }catch(e){console.error('Submit ack error:',e);}
}

function exp(){
  try{
    if(!data.length){alert('No data');return;}
    let csv='ID,Date,Time,Device,Dist,Lat,Lng,Severity,Status,Modified\\n';
    data.forEach(f=>{
      csv+=f.id+','+f.date+','+f.time+','+f.device+','+f.dist+','+
        f.lat+','+f.lng+','+f.sev+','+(f.status||'Pending')+','+(f.mod||'')+'\\n';
    });
    const blob=new Blob([csv],{type:'text/csv'});
    const url=URL.createObjectURL(blob);
    const a=document.createElement('a');
    a.href=url;a.download='faults_'+new Date().toISOString().split('T')[0]+'.csv';
    a.click();URL.revokeObjectURL(url);
  }catch(e){console.error('Export error:',e);}
}
function updateLoadStatus(msg){
  try{
    const el = document.getElementById('load-status');
    if(el) el.textContent = msg;
  }catch(e){
    console.error('Load status error:',e);
  }
}

function hideLoading(){
  try{
    const loader = document.getElementById('loading');
    if(loader){
      loader.classList.add('hide');
      setTimeout(()=>loader.style.display='none', 500);
    }
  }catch(e){
    console.error('Hide loading error:',e);
  }
}
window.addEventListener('load',init);
let osmLoaded = false;

async function fetchOSMPowerLines() {
  if (osmLoaded) return;
  
  try {
    document.getElementById('conn').textContent = 'Loading power lines...';
    
    const query = `[out:json][timeout:25];
      (
        way["power"="line"](12.2,122.5,14.5,124.5);
        way["power"="minor_line"](12.2,122.5,14.5,124.5);
      );
      out geom;`;
    
    const response = await fetch('https://overpass-api.de/api/interpreter', {
      method: 'POST',
      body: query
    });
    
    if (!response.ok) throw new Error('OSM API failed');
    
    const data = await response.json();
    let count = 0;
    
    data.elements.forEach(line => {
      if (line.type === 'way' && line.geometry && line.geometry.length > 1) {
        const coords = line.geometry.map(n => [n.lat, n.lon]);
        const voltage = line.tags.voltage || line.tags['voltage:primary'] || 'unknown';
        const cables = line.tags.cables || 'unknown';
        const operator = line.tags.operator || 'Unknown';
        
        // Determine color and weight by voltage
        let color, weight;
        const v = parseInt(voltage);
        
        if (v >= 230000 || voltage.includes('230')) {
          color = '#e74c3c'; weight = 5;
        } else if (v >= 69000 || voltage.includes('69')) {
          color = '#3498db'; weight = 4;
        } else if (v >= 34500 || voltage.includes('34.5') || voltage.includes('34500')) {
          color = '#2ecc71'; weight = 3;
        } else if (v >= 13800 || voltage.includes('13.8') || voltage.includes('13800')) {
          color = '#f39c12'; weight = 2;
        } else {
          color = '#95a5a6'; weight = 2;
        }
        
        const polyline = L.polyline(coords, {
          color: color,
          weight: weight,
          opacity: 0.7
        });
        
        polyline.bindPopup(
          '<b>⚡ Power Line</b><br>' +
          'Voltage: ' + voltage + '<br>' +
          'Cables: ' + cables + '<br>' +
          'Operator: ' + operator + '<br>' +
          'Source: OpenStreetMap'
        );
        
        transmissionLayer.addLayer(polyline);
        count++;
      }
    });
    
    osmLoaded = true;
    console.log('✓ Loaded ' + count + ' power lines from OSM');
    document.getElementById('conn').textContent = 'Connected';
    
  } catch (error) {
    console.error('OSM load failed:', error);
    document.getElementById('conn').textContent = 'OSM unavailable - using manual data';
    // Fall back to manual TRANSMISSION_LINES data
    drawTransmissionLines();
  }
}
</script></body></html>
"""


def main():
    api = Api()
    webview.create_window("Overwatch SCADA 2025", html=HTML, js_api=api, width=1500, height=850, resizable=True)
    webview.start(debug=True)


if __name__ == "__main__":
    main()