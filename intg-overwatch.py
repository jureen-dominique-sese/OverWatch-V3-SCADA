"""
Overwatch SCADA 2025 - IEEE 13 Node Test Feeder Edition
Integrated with MATLAB Simulation Logic
"""
import webview
import json
import random
import math
import cmath
import numpy as np
from datetime import datetime, timedelta

# --- 1. SIMULATION ENGINE (Ported from MATLAB) ---

class PowerSystem:
    def __init__(self):
        # Configuration from get_system_config.m
        self.V_LL = 13200           # 13.2 kV
        self.S_base = 5e6           # 5 MVA
        self.V_LN = self.V_LL / math.sqrt(3)
        self.I_base = self.S_base / (math.sqrt(3) * self.V_LL)
        self.Z_base = (self.V_LL**2) / self.S_base
        
        # Source Impedance (Stiff Source)
        MVA_SC = 250e6
        Z_src_mag = self.S_base / MVA_SC
        self.Z_source = Z_src_mag * complex(0.1, 0.99)
        
        # Line Impedance (Ohms/km converted to PU)
        R1_ohm = 0.19; X1_ohm = 0.40
        R0_ohm = 0.50; X0_ohm = 1.20
        self.z1_pu_km = complex(R1_ohm, X1_ohm) / self.Z_base
        self.z0_pu_km = complex(R0_ohm, X0_ohm) / self.Z_base
        
        # Database for Lookup
        self.db_SLG = []
        self.db_LL = []
        self.db_3PH = []
        self.generate_database()

    def calculate_current(self, dist_km, type_idx, rf_ohm=0):
        # 1=SLG, 2=LL, 3=3PH
        Z1_tot = self.Z_source + (self.z1_pu_km * dist_km)
        Z2_tot = Z1_tot
        Z0_tot = self.Z_source + (self.z0_pu_km * dist_km)
        Rf_pu = rf_ohm / self.Z_base
        V_f = 1.0 # 1.0 pu
        a = cmath.exp(complex(0, 2*math.pi/3)) # 120 deg operator
        
        I0 = I1 = I2 = 0j
        
        if type_idx == 1: # SLG (Phase A)
            denom = Z1_tot + Z2_tot + Z0_tot + (3 * Rf_pu)
            I1 = V_f / denom
            I2 = I1
            I0 = I1
        elif type_idx == 2: # LL (Phase B-C)
            I1 = V_f / (Z1_tot + Z2_tot + Rf_pu)
            I2 = -I1
            I0 = 0j
        elif type_idx == 3: # 3PH
            I1 = V_f / (Z1_tot + Rf_pu)
            I2 = 0j
            I0 = 0j
            
        # Symmetrical Components to Phase Currents
        # [Ia; Ib; Ic] = A * [I0; I1; I2]
        Ia = I0 + I1 + I2
        Ib = I0 + (a**2)*I1 + a*I2
        Ic = I0 + a*I1 + (a**2)*I2
        
        # Convert to Amps
        return [abs(Ia)*self.I_base, abs(Ib)*self.I_base, abs(Ic)*self.I_base]

    def generate_database(self):
        print("⚡ Generating Physics Lookup Table...")
        # Generate 0.01 to 10.0 km
        dist = np.arange(0.01, 10.0, 0.01)
        for d in dist:
            i_slg = self.calculate_current(d, 1)
            i_ll  = self.calculate_current(d, 2)
            i_3ph = self.calculate_current(d, 3)
            
            # Storing [dist, Ia, Ib, Ic]
            self.db_SLG.append([d, i_slg[0], i_slg[1], i_slg[2]])
            self.db_LL.append([d, i_ll[0], i_ll[1], i_ll[2]])
            self.db_3PH.append([d, i_3ph[0], i_3ph[1], i_3ph[2]])
        print("✓ Physics Engine Ready")

    def locate_fault(self, readings, sensor_km):
        # readings: [Ia, Ib, Ic] from the active sensor
        # sensor_km: location of that sensor
        
        I_max = max(readings)
        if I_max < 50: return None # No fault
        
        Ia, Ib, Ic = readings
        
        # Classification Logic (same as MATLAB)
        f_type = "Unknown"
        search_db = []
        target_val = 0
        col_idx = 0 # 0=Dist, 1=Ia, 2=Ib, 3=Ic
        
        if Ia > 0.5*I_max and Ib < 0.2*I_max and Ic < 0.2*I_max:
            f_type = "Single Line-to-Ground (Phase A)"
            search_db = self.db_SLG
            target_val = Ia
            col_idx = 1
        elif Ia < 0.2*I_max and Ib > 0.8*I_max and Ic > 0.8*I_max:
            f_type = "Line-to-Line (Phase B-C)"
            search_db = self.db_LL
            target_val = Ib
            col_idx = 2
        elif Ia > 0.9*I_max and Ib > 0.9*I_max and Ic > 0.9*I_max:
            f_type = "Three-Phase Balanced"
            search_db = self.db_3PH
            target_val = Ia
            col_idx = 1
        else:
            f_type = "Uncertain (Assumed SLG)"
            search_db = self.db_SLG
            target_val = I_max
            col_idx = 1
            
        # Pinpoint Location (Inverse Lookup)
        best_dist = 0
        min_diff = float('inf')
        
        for row in search_db:
            if row[0] < sensor_km: continue # Fault must be downstream
            diff = abs(row[col_idx] - target_val)
            if diff < min_diff:
                min_diff = diff
                best_dist = row[0]
                
        return {
            "status": "FAULT CONFIRMED",
            "type": f_type,
            "dist": best_dist,
            "amps": target_val
        }

# --- 2. API & STATE MANAGEMENT ---

class Api:
    def __init__(self):
        self.sys = PowerSystem()
        self.faults = []
        self.init_ieee13_map()
        
    def init_ieee13_map(self):
        # Base Lat/Lng (Bicol - Pili/Naga area for correlation)
        base_lat = 13.554725
        base_lng = 123.274724
        
        # Scaling factor (approx meters to deg)
        s = 0.000009 
        
        # Node Distances (from Node 650) & Layout coordinates
        # We manually map the IEEE 13 tree structure to X,Y offsets (meters)
        # 650 (0,0) -> 632 (East 600m)
        # 632 -> 671 (East 600m) -> 680 (South 300m)
        # ... etc
        
        self.nodes = {
            "650": {"lat": base_lat, "lng": base_lng, "dist_km": 0.0, "name": "Substation"},
            "632": {"lat": base_lat, "lng": base_lng + 600*s, "dist_km": 0.61, "name": "Node 632"}, # 2000ft
            "645": {"lat": base_lat + 150*s, "lng": base_lng + 750*s, "dist_km": 0.76, "name": "Node 645"},
            "646": {"lat": base_lat + 240*s, "lng": base_lng + 750*s, "dist_km": 0.85, "name": "Node 646"},
            "633": {"lat": base_lat - 150*s, "lng": base_lng + 600*s, "dist_km": 0.76, "name": "Node 633"},
            "634": {"lat": base_lat - 300*s, "lng": base_lng + 600*s, "dist_km": 0.76, "name": "XFM-1"}, # 0 dist from 633
            "671": {"lat": base_lat, "lng": base_lng + 1200*s, "dist_km": 1.22, "name": "Node 671"}, # 2000ft from 632
            "680": {"lat": base_lat - 300*s, "lng": base_lng + 1200*s, "dist_km": 1.52, "name": "Node 680"},
            "684": {"lat": base_lat + 90*s, "lng": base_lng + 1200*s, "dist_km": 1.31, "name": "Node 684"},
            "611": {"lat": base_lat + 90*s, "lng": base_lng + 1290*s, "dist_km": 1.40, "name": "Node 611"},
            "652": {"lat": base_lat + 330*s, "lng": base_lng + 1200*s, "dist_km": 1.55, "name": "Node 652"},
            "692": {"lat": base_lat, "lng": base_lng + 1200*s, "dist_km": 1.22, "name": "Switch"}, # At 671
            "675": {"lat": base_lat, "lng": base_lng + 1350*s, "dist_km": 1.37, "name": "Node 675"}
        }
        
        # Define Connectivity
        self.lines = [
            ["650", "632"], ["632", "645"], ["645", "646"],
            ["632", "633"], ["633", "634"], ["632", "671"],
            ["671", "680"], ["671", "684"], ["684", "611"],
            ["684", "652"], ["671", "692"], ["692", "675"]
        ]
        
        # Overwatch Units (Matching MATLAB config logic but mapped to IEEE nodes)
        # Unit 1: Source (650), Unit 2: Node 632, Unit 3: Node 671
        self.sensors = [
            {"id": "U1", "node": "650", "km": 0.0},
            {"id": "U2", "node": "632", "km": 0.61},
            {"id": "U3", "node": "671", "km": 1.22}
        ]

    def get_map_data(self):
        return {
            "nodes": self.nodes,
            "lines": self.lines,
            "sensors": self.sensors
        }

    def simulate_fault(self, node_id, fault_type_idx):
        """
        Runs the full MATLAB-equivalent simulation chain.
        1. Get physics distance of node.
        2. Calculate currents.
        3. Add noise.
        4. Run Locator Algorithm.
        """
        try:
            node = self.nodes[node_id]
            actual_km = node['dist_km']
            
            # A. PHYSICS SIMULATION (simulate_overwatch_network.m)
            # Find closest upstream unit to define what currents are seen
            active_sensor = None
            closest_dist = -1
            
            for s in self.sensors:
                if s['km'] <= actual_km and s['km'] > closest_dist:
                    active_sensor = s
                    closest_dist = s['km']
            
            if not active_sensor:
                return {"error": "Fault upstream of all sensors"}
                
            # Calculate perfect currents
            I_real = self.sys.calculate_current(actual_km, int(fault_type_idx))
            
            # Inject Noise (+/- 1%)
            noise = [1.0 + 0.01*random.uniform(-1, 1) for _ in range(3)]
            I_sensed = [I_real[i] * noise[i] for i in range(3)]
            
            # B. CPU ALGORITHM (cpu_fault_locator.m)
            result = self.sys.locate_fault(I_sensed, active_sensor['km'])
            
            if not result:
                return {"error": "Fault current too low to detect"}
                
            # C. CREATE REPORT
            new_id = f"FLT-{random.randint(1000,9999)}"
            report = {
                "id": new_id,
                "date": datetime.now().strftime("%Y-%m-%d"),
                "time": datetime.now().strftime("%H:%M:%S"),
                "device": f"Sensor {active_sensor['id']} ({active_sensor['node']})",
                "dist": round(result['dist'] * 1000, 2), # km to meters
                "lat": node['lat'], # In real life we'd calculate lat/lng from dist
                "lng": node['lng'], # mapping back to the node for viz
                "sev": "CRITICAL" if result['amps'] > 8000 else "WARNING",
                "status": "Pending",
                "type": result['type'],
                "amps": round(result['amps'], 2)
            }
            
            self.faults.append(report)
            return {"success": True, "report": report}
            
        except Exception as e:
            return {"error": str(e)}

    def get_faults(self):
        # Return local list instead of Google Sheets for this demo
        return self.faults

    def get_stats(self):
        return {
            "total": len(self.faults),
            "crit": len([f for f in self.faults if f['sev'] == 'CRITICAL']),
            "warn": len([f for f in self.faults if f['sev'] == 'WARNING']),
            "devs": {} # Simplified
        }
        
    def ack_fault(self, rid, status, name):
        for f in self.faults:
            if f['id'] == rid:
                f['status'] = status
                f['ack'] = True
                f['mod'] = name
                return {"ok": True}
        return {"ok": False, "err": "Not found"}

# --- 3. FRONTEND (HTML/JS) ---

HTML = """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Overwatch IEEE 13</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.css">
<script src="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
:root{--bg:#1e1e1e;--panel:#252526;--text:#ccc;--accent:#007acc;--crit:#f48771;--warn:#cca700;--ok:#89d185}
body{margin:0;background:var(--bg);color:var(--text);font-family:'Segoe UI',sans-serif;height:100vh;display:flex;flex-direction:column}
.head{height:48px;background:var(--panel);border-bottom:1px solid #333;display:flex;align-items:center;padding:0 20px;gap:20px}
.main{flex:1;display:flex;overflow:hidden}
#map{flex:1;background:#111}
.side{width:320px;background:var(--panel);border-left:1px solid #333;padding:20px;display:flex;flex-direction:column;gap:15px;overflow-y:auto}
.box{background:#333;padding:12px;border-radius:4px;font-size:12px}
.btn{width:100%;padding:8px;background:var(--accent);color:#fff;border:none;border-radius:3px;cursor:pointer;margin-top:5px}
.btn:hover{opacity:0.9}
.btn.sim{background:#d35400}
select, input{width:100%;padding:6px;background:#1e1e1e;border:1px solid #444;color:#fff;margin:5px 0}
.pulse{width:14px;height:14px;border-radius:50%;background:var(--crit);box-shadow:0 0 0 0 rgba(244,135,113,0.7);animation:p 1.5s infinite}
@keyframes p{0%{box-shadow:0 0 0 0 rgba(244,135,113,0.7)}70%{box-shadow:0 0 0 10px rgba(244,135,113,0)}100%{box-shadow:0 0 0 0 rgba(244,135,113,0)}}
.node-icon{width:10px;height:10px;background:#888;border-radius:50%;border:2px solid #fff}
.sensor-icon{font-size:14px}
</style>
</head><body>

<div class="head">
    <div style="font-weight:bold;color:var(--accent)">⚡ Overwatch SCADA</div>
    <div style="font-size:12px;color:#888">IEEE 13 Node Test Feeder Integration</div>
</div>

<div class="main">
    <div id="map"></div>
    <div class="side">
        
        <div>
            <h3 style="margin:0 0 10px 0;color:var(--accent)">🎮 Simulation Control</h3>
            <div class="box">
                <label>Target Node</label>
                <select id="sim-node"></select>
                <label>Fault Type</label>
                <select id="sim-type">
                    <option value="1">Single Line-to-Ground (A)</option>
                    <option value="2">Line-to-Line (B-C)</option>
                    <option value="3">Three-Phase</option>
                </select>
                <button class="btn sim" onclick="runSim()">⚡ Inject Fault</button>
            </div>
        </div>

        <div id="result-box" style="display:none">
            <h3 style="margin:0 0 10px 0">📋 Detection Report</h3>
            <div class="box">
                <div id="res-status" style="font-weight:bold;color:var(--crit)"></div>
                <div id="res-detail"></div>
            </div>
        </div>

        <div style="margin-top:auto">
            <h3>LOGS</h3>
            <div id="logs" style="font-size:11px;max-height:200px;overflow-y:auto"></div>
        </div>
    </div>
</div>

<script>
let map, nodes={}, lines=[], sensors=[];

async function init(){
    const data = await window.pywebview.api.get_map_data();
    nodes = data.nodes;
    
    // Initialize Map centered on Substation
    const sub = nodes["650"];
    map = L.map('map').setView([sub.lat, sub.lng], 15);
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',{
        attribution:'© OpenStreetMap, © CartoDB'
    }).addTo(map);

    // Draw Topology
    data.lines.forEach(l => {
        const n1 = nodes[l[0]];
        const n2 = nodes[l[1]];
        L.polyline([[n1.lat, n1.lng], [n2.lat, n2.lng]], {color:'#555', weight:4}).addTo(map);
    });

    // Draw Nodes & Populate Select
    const sel = document.getElementById('sim-node');
    for(let id in nodes){
        const n = nodes[id];
        L.marker([n.lat, n.lng], {
            icon: L.divIcon({className:'node-icon', iconSize:[10,10]})
        }).bindPopup(`<b>${n.name}</b><br>ID: ${id}`).addTo(map);
        
        // Add to dropdown (exclude substation 650 usually)
        if(id !== "650") {
            const opt = document.createElement('option');
            opt.value = id;
            opt.text = n.name + " (" + id + ")";
            sel.appendChild(opt);
        }
    }

    // Draw Sensors
    data.sensors.forEach(s => {
        const n = nodes[s.node];
        L.marker([n.lat, n.lng], {
            icon: L.divIcon({html:'📡', className:'sensor-icon', iconSize:[20,20]})
        }).addTo(map).bindPopup(`<b>Overwatch Unit ${s.id}</b>`);
    });
}

async function runSim(){
    const node = document.getElementById('sim-node').value;
    const type = document.getElementById('sim-type').value;
    
    document.getElementById('result-box').style.display='block';
    document.getElementById('res-status').innerText = "Calculating...";
    document.getElementById('res-detail').innerText = "";
    
    const res = await window.pywebview.api.simulate_fault(node, type);
    
    if(res.error){
        document.getElementById('res-status').innerText = "❌ ERROR";
        document.getElementById('res-detail').innerText = res.error;
    } else {
        const r = res.report;
        document.getElementById('res-status').innerText = "⚠️ " + r.status.toUpperCase();
        document.getElementById('res-detail').innerHTML = 
            `<b>Type:</b> ${r.type}<br>` +
            `<b>Est. Dist:</b> ${r.dist} m<br>` +
            `<b>Current:</b> ${r.amps} A`;
            
        // Map Visualization
        L.marker([r.lat, r.lng], {
            icon: L.divIcon({className:'pulse', iconSize:[20,20]})
        }).addTo(map).bindPopup(`<b>FAULT DETECTED</b><br>${r.type}`);
        
        // Add Log
        const log = document.getElementById('logs');
        log.innerHTML = `<div style="border-bottom:1px solid #444;padding:4px">
            <span style="color:var(--crit)">[${r.time}]</span> Fault at ${node} (${r.dist}m)
        </div>` + log.innerHTML;
    }
}

window.onload = init;
</script>
</body></html>
"""

if __name__ == '__main__':
    api = Api()
    webview.create_window('Overwatch SCADA - IEEE 13 Feeder', html=HTML, js_api=api, width=1200, height=800)
    webview.start()