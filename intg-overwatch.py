"""
Tactical SCADA Dashboard - IEEE 13 Node Test Feeder
Real-time Google Sheets Integration with Leaflet Simple CRS
"""

import webview
import requests
import csv
import io
from datetime import datetime
import json
import math
import threading
import time

# ============================================================================
# POWER SYSTEM PHYSICS ENGINE
# ============================================================================

class PowerSystem:
    """
    IEEE 13 Node Test Feeder - Fault Current Calculator
    Based on sequence impedance matrices from get_system_config.m
    """
    
    def __init__(self):
        # System parameters
        self.V_LL = 13200  # Line-to-Line Voltage (V)
        self.S_base = 5e6  # Base MVA
        self.F_Hz = 60
        self.V_LN = self.V_LL / math.sqrt(3)
        self.I_base = self.S_base / (math.sqrt(3) * self.V_LL)
        self.Z_base = (self.V_LL ** 2) / self.S_base
        
        # Source impedance (250 MVA short circuit capacity)
        MVA_SC = 250e6
        Z_source_mag = self.S_base / MVA_SC
        self.Z_source = complex(0.1 * Z_source_mag, 0.99 * Z_source_mag)
        
        # Line impedances per km (from get_system_config.m)
        R1_ohm_km = 0.19
        X1_ohm_km = 0.40
        self.z1_pu_km = complex(R1_ohm_km, X1_ohm_km) / self.Z_base
        
        # IEEE 13 Node estimated line lengths (km)
        self.line_lengths = {
            '650-632': 2.0,
            '632-633': 1.8,
            '632-645': 1.5,
            '632-671': 2.2,
            '645-646': 1.0,
            '671-680': 2.8,
            '671-684': 1.4,
            '684-611': 1.0,
            '684-652': 1.2,
            '633-634': 0.6
        }
    
    def calculate_fault_current(self, bus_name, fault_type='3LG'):
        """
        Calculate fault current at specified bus
        
        Args:
            bus_name: Bus number (e.g., '632', '671')
            fault_type: '3LG', 'SLG', 'LL', 'LLG'
        
        Returns:
            dict with magnitude (A), severity, impedance
        """
        # Get path impedance from substation to fault
        Z_path = self._get_path_impedance(bus_name)
        Z_total = self.Z_source + Z_path
        
        # Fault current in per-unit
        if abs(Z_total) < 1e-6:
            I_fault_pu = 0
        else:
            I_fault_pu = 1.0 / abs(Z_total)
        
        # Convert to actual amperes
        I_fault_A = I_fault_pu * self.I_base
        
        # Determine severity
        if I_fault_A > 8000:
            severity = "CRITICAL"
        elif I_fault_A > 5000:
            severity = "WARNING"
        elif I_fault_A > 3000:
            severity = "CAUTION"
        else:
            severity = "INFO"
        
        return {
            'magnitude': round(I_fault_A, 2),
            'severity': severity,
            'impedance_pu': round(abs(Z_total), 4),
            'type': fault_type,
            'voltage_drop_pct': round((I_fault_pu * abs(Z_path)) * 100, 2)
        }
    
    def _get_path_impedance(self, bus_name):
        """Calculate total impedance from Bus 650 to target bus"""
        # Network tree paths
        paths = {
            '650': [],
            '632': ['650-632'],
            '633': ['650-632', '632-633'],
            '634': ['650-632', '632-633', '633-634'],
            '645': ['650-632', '632-645'],
            '646': ['650-632', '632-645', '645-646'],
            '671': ['650-632', '632-671'],
            '680': ['650-632', '632-671', '671-680'],
            '684': ['650-632', '632-671', '671-684'],
            '611': ['650-632', '632-671', '671-684', '684-611'],
            '652': ['650-632', '632-671', '671-684', '684-652']
        }
        
        path = paths.get(bus_name, [])
        Z_total = complex(0, 0)
        
        for segment in path:
            length_km = self.line_lengths.get(segment, 1.0)
            Z_total += self.z1_pu_km * length_km
        
        return Z_total


# ============================================================================
# TOPOLOGY MANAGER
# ============================================================================

class MapManager:
    """
    IEEE 13 Node topology with exact coordinate placement
    Coordinates match physics simulation in get_system_config.m
    """
    
    def __init__(self):
        # Fixed anchor coordinates (X, Y)
        self.nodes = {
            '650': {'x': 0, 'y': 0, 'type': 'substation', 'voltage': 115, 'name': 'Substation'},
            '680': {'x': 0, 'y': 5290, 'type': 'load', 'voltage': 13.2, 'name': 'End Node'},
            '646': {'x': 1215, 'y': 3005, 'type': 'load', 'voltage': 13.2, 'name': 'Load 646'},
            '634': {'x': -1905, 'y': 3005, 'type': 'transformer', 'voltage': 13.2, 'name': 'XFM-1'},
            
            # Interpolated intermediate nodes
            '632': {'x': 0, 'y': 2000, 'type': 'junction', 'voltage': 13.2, 'name': 'Junction 632'},
            '633': {'x': -950, 'y': 3005, 'type': 'junction', 'voltage': 13.2, 'name': 'Junction 633'},
            '645': {'x': 600, 'y': 3005, 'type': 'junction', 'voltage': 13.2, 'name': 'Junction 645'},
            '671': {'x': 0, 'y': 3500, 'type': 'junction', 'voltage': 13.2, 'name': 'Junction 671'},
            '684': {'x': 800, 'y': 4200, 'type': 'junction', 'voltage': 13.2, 'name': 'Junction 684'},
            '611': {'x': 1400, 'y': 4500, 'type': 'load', 'voltage': 13.2, 'name': 'Load 611'},
            '652': {'x': 1200, 'y': 4800, 'type': 'load', 'voltage': 13.2, 'name': 'Load 652'}
        }
        
        # Network connections (edges)
        self.connections = [
            ['650', '632'],
            ['632', '633'],
            ['632', '645'],
            ['632', '671'],
            ['633', '634'],
            ['645', '646'],
            ['671', '680'],
            ['671', '684'],
            ['684', '611'],
            ['684', '652']
        ]
    
    def get_topology(self):
        """Return complete topology for frontend"""
        return {
            'nodes': self.nodes,
            'connections': self.connections
        }


# ============================================================================
# GOOGLE SHEETS DATA CONNECTOR
# ============================================================================

class DataConnector:
    """
    Fetches live fault data from Google Sheets
    Silently refreshes every 1 second
    """
    
    def __init__(self, sheet_id, sheet_name):
        self.sheet_id = sheet_id
        self.sheet_name = sheet_name
        self.cache = []
        self.last_fetch = None
    
    def fetch_data(self):
        """
        Fetch data from Google Sheets via CSV export
        
        Column mapping (UPDATED):
        - ReportID (A) -> id
        - Date (B) -> date
        - Time (C) -> time
        - Lat(x) (D) -> x (map X coordinate)
        - Long(y) (E) -> y (map Y coordinate)
        - Fault Type (F) -> fault_type
        - Modified By (G) -> modified_by
        - Status (H) -> status
        """
        url = f"https://docs.google.com/spreadsheets/d/{self.sheet_id}/gviz/tq?tqx=out:csv&sheet={self.sheet_name}"
        
        try:
            response = requests.get(url, timeout=3)
            response.raise_for_status()
            
            reader = csv.DictReader(io.StringIO(response.text))
            data = []
            
            for row in reader:
                try:
                    # Parse columns correctly
                    report_id = row.get('ReportID', 'UNKNOWN').strip()
                    
                    # CORRECTED: Get X from Lat(x) column and Y from Long(y) column
                    x_coord = float(row.get('Lat(x)', 0))  # This is X on the map
                    y_coord = float(row.get('Long(y)', 0))  # This is Y on the map
                    
                    fault_type = row.get('Fault Type', '').strip()
                    status = row.get('Status', '').strip().upper() if row.get('Status') else 'ACTIVE FAULT'
                    
                    fault = {
                        'id': report_id,
                        'date': row.get('Date', datetime.now().strftime('%Y-%m-%d')),
                        'time': row.get('Time', datetime.now().strftime('%H:%M:%S')),
                        'device': 'SimDev',  # Default device name
                        'x': x_coord,  # Map X coordinate
                        'y': y_coord,  # Map Y coordinate
                        'distance': 0,  # Can be calculated if needed
                        'fault_type': fault_type,
                        'status': status if status else 'ACTIVE FAULT',
                        'modified_by': row.get('Modified By', '').strip(),
                        'timestamp': datetime.now().isoformat()
                    }
                    
                    # Determine severity from fault type
                    if 'LLG' in fault_type or 'Phase B-C' in fault_type:
                        fault['severity'] = 'CRITICAL'
                    elif 'SLG' in fault_type or 'Phase A' in fault_type:
                        fault['severity'] = 'WARNING'
                    else:
                        fault['severity'] = 'INFO'
                    
                    # Override severity based on status
                    if status == 'RESOLVED':
                        fault['severity'] = 'INFO'
                    elif status == 'ACTIVE FAULT':
                        # Keep the severity from fault type
                        pass
                    
                    data.append(fault)
                    
                except (ValueError, KeyError) as e:
                    print(f"⚠ Row parse error: {e}")
                    print(f"   Row data: {row}")
                    continue
            
            self.cache = data
            self.last_fetch = datetime.now()
            return data
            
        except Exception as e:
            print(f"⚠ Fetch error: {e}")
            return self.cache

# ============================================================================
# PYWEBVIEW API BRIDGE
# ============================================================================

class Api:
    """
    Python API exposed to JavaScript frontend
    Handles real-time data updates and simulation
    """
    
    def __init__(self):
        self.power_system = PowerSystem()
        self.map_manager = MapManager()
        self.data_connector = DataConnector(
            sheet_id="1UTQUNv0z8m293VNw5tuJzkcxGnbNuV4zUYSV0MsrOQw",
            sheet_name="inputLog"
        )
        self.auto_refresh = True
    
    def get_topology(self):
        """Return IEEE 13 node topology"""
        return self.map_manager.get_topology()
    
    def get_faults(self):
        """Fetch current fault data (called repeatedly by frontend)"""
        return self.data_connector.fetch_data()
    
    def simulate_fault(self, bus_name, fault_type='3LG'):
        """
        Generate simulated fault for testing
        
        Args:
            bus_name: Bus number (e.g., '632')
            fault_type: Fault type ('3LG', 'SLG', etc.)
        """
        result = self.power_system.calculate_fault_current(bus_name, fault_type)
        
        # Get bus coordinates
        node = self.map_manager.nodes.get(bus_name, {'x': 0, 'y': 0})
        
        return {
            'id': f'SIM-{bus_name}-{datetime.now().strftime("%H%M%S")}',
            'date': datetime.now().strftime('%Y-%m-%d'),
            'time': datetime.now().strftime('%H:%M:%S'),
            'device': f'Bus {bus_name}',
            'x': node['x'],
            'y': node['y'],
            'distance': 0,
            'status': 'SIMULATED',
            'severity': result['severity'],
            'fault_current': result['magnitude'],
            'impedance': result['impedance_pu'],
            'voltage_drop': result['voltage_drop_pct'],
            'fault_type': fault_type
        }
    
    def get_system_status(self):
        """Return overall system health metrics"""
        faults = self.data_connector.cache
        
        critical = sum(1 for f in faults if f.get('severity') == 'CRITICAL')
        warnings = sum(1 for f in faults if f.get('severity') == 'WARNING')
        
        return {
            'total_faults': len(faults),
            'critical': critical,
            'warnings': warnings,
            'system_voltage': 13.2,
            'frequency': 60.0,
            'last_update': self.data_connector.last_fetch.isoformat() if self.data_connector.last_fetch else None,
            'timestamp': datetime.now().isoformat()
        }
    
    def get_bus_list(self):
        """Return list of all buses for simulation dropdown"""
        return list(self.map_manager.nodes.keys())


# ============================================================================
# HTML FRONTEND WITH TACTICAL HUD
# ============================================================================

HTML = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>TACTICAL SCADA - IEEE 13 Node</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.css">
    <script src="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap" rel="stylesheet">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Share Tech Mono', monospace;
        }
        
        body {
            background: #0b0c10;
            color: #66fcf1;
            overflow: hidden;
        }
        
        /* ===== MAP WITH TACTICAL GRID ===== */
        #map {
            width: 100%;
            height: 100vh;
            background: 
                linear-gradient(0deg, rgba(102, 252, 241, 0.03) 1px, transparent 1px),
                linear-gradient(90deg, rgba(102, 252, 241, 0.03) 1px, transparent 1px);
            background-size: 100px 100px;
            background-color: #0b0c10;
        }
        
        /* ===== SCANLINE OVERLAY ===== */
        #map::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: repeating-linear-gradient(
                0deg,
                rgba(0, 0, 0, 0.1),
                rgba(0, 0, 0, 0.1) 1px,
                transparent 1px,
                transparent 3px
            );
            pointer-events: none;
            z-index: 1000;
            animation: scanline 10s linear infinite;
        }
        
        @keyframes scanline {
            0% { transform: translateY(0); }
            100% { transform: translateY(100px); }
        }
        
        /* ===== VIGNETTE EFFECT ===== */
        #map::after {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            box-shadow: inset 0 0 200px rgba(0, 0, 0, 0.9);
            pointer-events: none;
            z-index: 999;
        }
        
        /* ===== HUD CORNER BRACKETS ===== */
        .hud-corner {
            position: fixed;
            width: 50px;
            height: 50px;
            border: 3px solid #66fcf1;
            z-index: 2000;
            pointer-events: none;
            box-shadow: 0 0 10px #66fcf1;
        }
        
        .hud-corner.tl {
            top: 20px;
            left: 20px;
            border-right: none;
            border-bottom: none;
        }
        
        .hud-corner.tr {
            top: 20px;
            right: 20px;
            border-left: none;
            border-bottom: none;
        }
        
        .hud-corner.bl {
            bottom: 20px;
            left: 20px;
            border-right: none;
            border-top: none;
        }
        
        .hud-corner.br {
            bottom: 20px;
            right: 20px;
            border-left: none;
            border-top: none;
        }
        
        /* ===== TARGETING CROSSHAIR ===== */
        .crosshair {
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: 80px;
            height: 80px;
            border: 2px solid rgba(102, 252, 241, 0.4);
            border-radius: 50%;
            z-index: 1500;
            pointer-events: none;
        }
        
        .crosshair::before,
        .crosshair::after {
            content: '';
            position: absolute;
            background: rgba(102, 252, 241, 0.4);
        }
        
        .crosshair::before {
            top: 50%;
            left: 0;
            width: 100%;
            height: 2px;
            transform: translateY(-50%);
        }
        
        .crosshair::after {
            left: 50%;
            top: 0;
            width: 2px;
            height: 100%;
            transform: translateX(-50%);
        }
        
        .crosshair-center {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: 6px;
            height: 6px;
            background: #66fcf1;
            border-radius: 50%;
            box-shadow: 0 0 10px #66fcf1;
        }
        
        /* ===== TOP HUD BAR ===== */
        .hud-top {
            position: fixed;
            top: 0;
            left: 0;
            right: 400px;
            height: 70px;
            background: rgba(11, 12, 16, 0.95);
            border-bottom: 2px solid #66fcf1;
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 80px;
            z-index: 2000;
        }
        
        .hud-title {
            font-size: 24px;
            color: #66fcf1;
            text-shadow: 0 0 15px #66fcf1;
            letter-spacing: 4px;
            animation: pulse-glow 2s ease-in-out infinite;
        }
        
        @keyframes pulse-glow {
            0%, 100% { text-shadow: 0 0 15px #66fcf1; }
            50% { text-shadow: 0 0 25px #66fcf1, 0 0 35px #66fcf1; }
        }
        
        .hud-status {
            display: flex;
            gap: 30px;
            font-size: 13px;
        }
        
        .status-item {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .status-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            animation: blink 1.5s ease-in-out infinite;
        }
        
        .status-dot.online {
            background: #00ff41;
            box-shadow: 0 0 10px #00ff41;
        }
        
        .status-dot.critical {
            background: #ff4d4d;
            box-shadow: 0 0 10px #ff4d4d;
        }
        
        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.3; }
        }
        
        /* ===== RIGHT SIDE PANEL (LIVE FEED) ===== */
        .side-panel {
            position: fixed;
            top: 0;
            right: 0;
            width: 400px;
            height: 100vh;
            background: rgba(11, 12, 16, 0.98);
            border-left: 2px solid #66fcf1;
            z-index: 2000;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }
        
        .panel-header {
            padding: 20px;
            border-bottom: 2px solid #66fcf1;
            font-size: 16px;
            letter-spacing: 2px;
            text-align: center;
            color: #66fcf1;
            text-shadow: 0 0 10px #66fcf1;
        }
        
        .live-feed {
            flex: 1;
            overflow-y: auto;
            padding: 15px;
            display: flex;
            flex-direction: column;
            gap: 10px;
        }
        
        .feed-item {
            background: rgba(102, 252, 241, 0.05);
            border-left: 3px solid #66fcf1;
            padding: 12px;
            font-size: 11px;
            line-height: 1.6;
            animation: slide-in 0.3s ease-out;
        }
        
        .feed-item.critical {
            border-left-color: #ff4d4d;
            background: rgba(255, 77, 77, 0.1);
        }
        
        .feed-item.warning {
            border-left-color: #ffa500;
            background: rgba(255, 165, 0, 0.1);
        }
        
        @keyframes slide-in {
            from {
                opacity: 0;
                transform: translateX(20px);
            }
            to {
                opacity: 1;
                transform: translateX(0);
            }
        }
        
        .feed-item-id {
            font-weight: bold;
            color: #66fcf1;
            margin-bottom: 5px;
        }
        
        .feed-item-coord {
            color: #00ff41;
            font-family: monospace;
        }
        
        /* ===== SIMULATION PANEL ===== */
        .sim-panel {
            padding: 20px;
            border-top: 2px solid #66fcf1;
            background: rgba(11, 12, 16, 1);
        }
        
        .sim-panel h3 {
            font-size: 14px;
            margin-bottom: 15px;
            color: #66fcf1;
            letter-spacing: 2px;
        }
        
        .sim-control {
            display: flex;
            flex-direction: column;
            gap: 10px;
        }
        
        .sim-select {
            padding: 10px;
            background: rgba(102, 252, 241, 0.1);
            border: 1px solid #66fcf1;
            color: #66fcf1;
            font-family: 'Share Tech Mono', monospace;
            font-size: 12px;
            cursor: pointer;
        }
        
        .sim-select option {
            background: #0b0c10;
        }
        
        .sim-btn {
            padding: 12px;
            background: #66fcf1;
            color: #0b0c10;
            border: none;
            font-family: 'Share Tech Mono', monospace;
            font-size: 12px;
            font-weight: bold;
            cursor: pointer;
            letter-spacing: 2px;
            transition: all 0.3s;
        }
        
        .sim-btn:hover {
            background: #00ff41;
            box-shadow: 0 0 20px #00ff41;
        }
        
        .sim-btn:active {
            transform: scale(0.95);
        }
        
        /* ===== BOTTOM STATUS BAR ===== */
        .status-bar {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 400px;
            height: 40px;
            background: rgba(11, 12, 16, 0.95);
            border-top: 2px solid #66fcf1;
            display: flex;
            align-items: center;
            padding: 0 80px;
            gap: 30px;
            font-size: 11px;
            z-index: 2000;
        }
        
        .coord-display {
            color: #00ff41;
            font-family: monospace;
        }
        
        /* ===== CUSTOM LEAFLET STYLES ===== */
        .leaflet-container {
            background: transparent !important;
        }
        
        .leaflet-popup-content-wrapper {
            background: rgba(11, 12, 16, 0.95);
            color: #66fcf1;
            border: 2px solid #66fcf1;
            box-shadow: 0 0 20px rgba(102, 252, 241, 0.5);
            font-family: 'Share Tech Mono', monospace;
            font-size: 12px;
        }
        
        .leaflet-popup-tip {
            background: rgba(11, 12, 16, 0.95);
            border: 2px solid #66fcf1;
        }
        
        /* ===== SCROLLBAR ===== */
        .live-feed::-webkit-scrollbar {
            width: 8px;
        }
        
        .live-feed::-webkit-scrollbar-track {
            background: rgba(102, 252, 241, 0.05);
        }
        
        .live-feed::-webkit-scrollbar-thumb {
            background: #66fcf1;
            border-radius: 4px;
        }
        
        .live-feed::-webkit-scrollbar-thumb:hover {
            background: #00ff41;
        }
    </style>
</head>
<body>
    <!-- HUD CORNER BRACKETS -->
    <div class="hud-corner tl"></div>
    <div class="hud-corner tr"></div>
    <div class="hud-corner bl"></div>
    <div class="hud-corner br"></div>
    
    <!-- TARGETING CROSSHAIR -->
    <div class="crosshair">
        <div class="crosshair-center"></div>
    </div>
    
    <!-- TOP HUD BAR -->
    <div class="hud-top">
        <div class="hud-title">⚡ TACTICAL SCADA - IEEE 13</div>
        <div class="hud-status">
            <div class="status-item">
                <div class="status-dot online"></div>
                <span>SYSTEM: <span id="system-status">ONLINE</span></span>
            </div>
            <div class="status-item">
                <span>VOLTAGE: <span id="voltage-display">13.2 kV</span></span>
            </div>
            <div class="status-item">
                <span>FAULTS: <span id="fault-count">0</span></span>
            </div>
        </div>
    </div>
    
    <!-- MAP CONTAINER -->
    <div id="map"></div>
    
    <!-- RIGHT SIDE PANEL -->
    <div class="side-panel">
        <div class="panel-header">📡 LIVE FEED</div>
        <div class="live-feed" id="live-feed">
            <div class="feed-item">
                <div class="feed-item-id">SYSTEM INITIALIZED</div>
                <div>Awaiting fault data...</div>
            </div>
        </div>
        
        <!-- SIMULATION PANEL -->
        <div class="sim-panel">
            <h3>🎮 FAULT SIMULATOR</h3>
            <div class="sim-control">
                <select class="sim-select" id="bus-select">
                    <option value="">Select Bus...</option>
                </select>
                <select class="sim-select" id="fault-type">
                    <option value="3LG">3-Phase Ground Fault (3LG)</option>
                    <option value="SLG">Single Line-Ground (SLG)</option>
                    <option value="LL">Line-to-Line (LL)</option>
                    <option value="LLG">Double Line-Ground (LLG)</option>
                </select>
                <button class="sim-btn" onclick="injectFault()">INJECT FAULT</button>
            </div>
        </div>
    </div>
    
    <!-- BOTTOM STATUS BAR -->
    <div class="status-bar">
        <div><span class="status-dot online"></span> CONNECTED</div>
        <div>FREQ: 60.0 Hz</div>
        <div class="coord-display">CURSOR: <span id="cursor-coord">---, ---</span></div>
        <div style="margin-left: auto;">LAST UPDATE: <span id="last-update">--:--:--</span></div>
    </div>

    <script>
        let map, markers = [], lines = [], topology = null;
        let faultData = [];
        let updateInterval = null;
        
// ===== INITIALIZE MAP WITH SIMPLE CRS =====
        function initMap() {
            // Use Simple CRS for Cartesian coordinates
            map = L.map('map', {
                crs: L.CRS.Simple,
                minZoom: -5,
                maxZoom: 2,
                zoomControl: true,
                attributionControl: false
            });
            
            // Set initial bounds to show entire network
            const bounds = [[-2000, -2500], [6000, 2500]];
            map.fitBounds(bounds);
            
            // Track cursor coordinates
            map.on('mousemove', function(e) {
                const coord = e.latlng;
                document.getElementById('cursor-coord').textContent = 
                    `X: ${Math.round(coord.lng)}, Y: ${Math.round(coord.lat)}`;
            });
            
            console.log('✓ Map initialized with Simple CRS');
        }
        
        // ===== DRAW IEEE 13 NODE TOPOLOGY =====
        async function drawTopology() {
            try {
                topology = await window.pywebview.api.get_topology();
                
                // Draw connections (lines)
                topology.connections.forEach(([busA, busB]) => {
                    const nodeA = topology.nodes[busA];
                    const nodeB = topology.nodes[busB];
                    
                    if (nodeA && nodeB) {
                        const line = L.polyline(
                            [[nodeA.y, nodeA.x], [nodeB.y, nodeB.x]],
                            {
                                color: '#66fcf1',
                                weight: 3,
                                opacity: 0.6
                            }
                        ).addTo(map);
                        
                        lines.push(line);
                    }
                });
                
                // Draw nodes (markers)
                Object.entries(topology.nodes).forEach(([busId, node]) => {
                    const iconColor = node.type === 'substation' ? '#00ff41' : 
                                     node.type === 'transformer' ? '#ffa500' :
                                     node.type === 'load' ? '#ff4d4d' : '#66fcf1';
                    
                    const icon = L.divIcon({
                        html: `<div style="
                            width: 16px;
                            height: 16px;
                            background: ${iconColor};
                            border: 2px solid #fff;
                            border-radius: 50%;
                            box-shadow: 0 0 15px ${iconColor};
                        "></div>`,
                        className: '',
                        iconSize: [16, 16],
                        iconAnchor: [8, 8]
                    });
                    
                    const marker = L.marker([node.y, node.x], {icon: icon}).addTo(map);
                    
                    // Tooltip on hover
                    marker.bindPopup(`
                        <div style="padding: 10px;">
                            <div style="font-size: 14px; font-weight: bold; margin-bottom: 8px;">
                                BUS ${busId}
                            </div>
                            <div style="line-height: 1.8;">
                                <div>Name: ${node.name}</div>
                                <div>Type: ${node.type.toUpperCase()}</div>
                                <div>Voltage: ${node.voltage} kV</div>
                                <div style="color: #00ff41;">Status: NOMINAL</div>
                                <div style="color: #666; margin-top: 5px;">
                                    Coord: (${node.x}, ${node.y})
                                </div>
                            </div>
                        </div>
                    `);
                    
                    markers.push(marker);
                });
                
                console.log('✓ Topology drawn: ' + Object.keys(topology.nodes).length + ' nodes');
                
            } catch (error) {
                console.error('❌ Topology draw error:', error);
            }
        }
        
        // ===== UPDATE FAULT DATA (REAL-TIME) =====
        async function updateFaults() {
            try {
                const newFaults = await window.pywebview.api.get_faults();
                
                // Update fault markers
                // Remove old fault markers (keep topology markers)
                markers.forEach(m => {
                    if (m.options && m.options.isFault) {
                        map.removeLayer(m);
                    }
                });
                markers = markers.filter(m => !m.options || !m.options.isFault);
                
                // Add new fault markers
                newFaults.forEach(fault => {
                    const color = fault.severity === 'CRITICAL' ? '#ff4d4d' :
                                 fault.severity === 'WARNING' ? '#ffa500' :
                                 fault.severity === 'CAUTION' ? '#ffff00' : '#66fcf1';
                    
                    const icon = L.divIcon({
                        html: `<div style="
                            width: 24px;
                            height: 24px;
                            background: ${color};
                            border: 3px solid #fff;
                            border-radius: 50%;
                            box-shadow: 0 0 20px ${color};
                            animation: pulse 1.5s ease-in-out infinite;
                        "></div>
                        <style>
                            @keyframes pulse {
                                0%, 100% { transform: scale(1); opacity: 1; }
                                50% { transform: scale(1.3); opacity: 0.7; }
                            }
                        </style>`,
                        className: '',
                        iconSize: [24, 24],
                        iconAnchor: [12, 12]
                    });
                    
                    const marker = L.marker([fault.y, fault.x], {
                        icon: icon,
                        isFault: true
                    }).addTo(map);
                    
                    marker.bindPopup(`
                        <div style="padding: 10px;">
                            <div style="font-size: 14px; font-weight: bold; margin-bottom: 8px; color: ${color};">
                                ${fault.severity} FAULT
                            </div>
                            <div style="line-height: 1.8;">
                                <div>ID: ${fault.id}</div>
                                <div>Device: ${fault.device}</div>
                                <div>Distance: ${fault.distance} m</div>
                                <div>Status: ${fault.status}</div>
                                <div>Time: ${fault.time}</div>
                                <div style="color: #00ff41; margin-top: 5px;">
                                    Coord: (${Math.round(fault.x)}, ${Math.round(fault.y)})
                                </div>
                            </div>
                        </div>
                    `);
                    
                    markers.push(marker);
                });
                
                // Update live feed
                updateLiveFeed(newFaults);
                
                // Update status
                const status = await window.pywebview.api.get_system_status();
                document.getElementById('fault-count').textContent = status.total_faults;
                document.getElementById('last-update').textContent = new Date().toLocaleTimeString();
                
                if (status.critical > 0) {
                    document.getElementById('system-status').textContent = 'CRITICAL';
                    document.getElementById('system-status').style.color = '#ff4d4d';
                } else if (status.warnings > 0) {
                    document.getElementById('system-status').textContent = 'WARNING';
                    document.getElementById('system-status').style.color = '#ffa500';
                } else {
                    document.getElementById('system-status').textContent = 'ONLINE';
                    document.getElementById('system-status').style.color = '#00ff41';
                }
                
            } catch (error) {
                console.error('❌ Fault update error:', error);
            }
        }
        
        // ===== UPDATE LIVE FEED PANEL =====
        function updateLiveFeed(faults) {
            const feed = document.getElementById('live-feed');
            
            // Only add new faults to feed (check if already displayed)
            const existingIds = Array.from(feed.querySelectorAll('.feed-item-id'))
                .map(el => el.textContent);
            
            faults.reverse().forEach(fault => {
                if (!existingIds.includes(fault.id)) {
                    const item = document.createElement('div');
                    item.className = `feed-item ${fault.severity.toLowerCase()}`;
                    item.innerHTML = `
                        <div class="feed-item-id">${fault.id}</div>
                        <div>Severity: ${fault.severity}</div>
                        <div>Device: ${fault.device}</div>
                        <div class="feed-item-coord">X: ${Math.round(fault.x)}, Y: ${Math.round(fault.y)}</div>
                        <div>Distance: ${fault.distance} m</div>
                        <div>Status: ${fault.status}</div>
                        <div style="color: #666; margin-top: 5px; font-size: 10px;">${fault.time}</div>
                    `;
                    feed.insertBefore(item, feed.firstChild);
                    
                    // Keep feed limited to 50 items
                    if (feed.children.length > 50) {
                        feed.removeChild(feed.lastChild);
                    }
                }
            });
        }
        
        // ===== INJECT SIMULATED FAULT =====
        async function injectFault() {
            const busSelect = document.getElementById('bus-select');
            const faultType = document.getElementById('fault-type');
            
            if (!busSelect.value) {
                alert('Please select a bus');
                return;
            }
            
            try {
                const result = await window.pywebview.api.simulate_fault(
                    busSelect.value,
                    faultType.value
                );
                
                console.log('✓ Simulated fault injected:', result);
                
                // Add to live feed immediately
                const feed = document.getElementById('live-feed');
                const item = document.createElement('div');
                item.className = `feed-item ${result.severity.toLowerCase()}`;
                item.innerHTML = `
                    <div class="feed-item-id">${result.id}</div>
                    <div>Severity: ${result.severity}</div>
                    <div>Bus: ${result.device}</div>
                    <div>Fault Type: ${result.fault_type}</div>
                    <div>Current: ${result.fault_current} A</div>
                    <div>Impedance: ${result.impedance} PU</div>
                    <div>Voltage Drop: ${result.voltage_drop}%</div>
                    <div class="feed-item-coord">X: ${Math.round(result.x)}, Y: ${Math.round(result.y)}</div>
                    <div style="color: #666; margin-top: 5px; font-size: 10px;">${result.time}</div>
                `;
                feed.insertBefore(item, feed.firstChild);
                
                // Add marker to map
                const color = result.severity === 'CRITICAL' ? '#ff4d4d' :
                             result.severity === 'WARNING' ? '#ffa500' : '#66fcf1';
                
                const icon = L.divIcon({
                    html: `<div style="
                        width: 24px;
                        height: 24px;
                        background: ${color};
                        border: 3px solid #fff;
                        border-radius: 50%;
                        box-shadow: 0 0 20px ${color};
                        animation: pulse 1.5s ease-in-out infinite;
                    "></div>`,
                    className: '',
                    iconSize: [24, 24],
                    iconAnchor: [12, 12]
                });
                
                const marker = L.marker([result.y, result.x], {
                    icon: icon,
                    isFault: true
                }).addTo(map);
                
                marker.bindPopup(`
                    <div style="padding: 10px;">
                        <div style="font-size: 14px; font-weight: bold; margin-bottom: 8px; color: ${color};">
                            SIMULATED ${result.severity} FAULT
                        </div>
                        <div style="line-height: 1.8;">
                            <div>ID: ${result.id}</div>
                            <div>Bus: ${result.device}</div>
                            <div>Type: ${result.fault_type}</div>
                            <div>Current: ${result.fault_current} A</div>
                            <div>Impedance: ${result.impedance} PU</div>
                            <div>V-Drop: ${result.voltage_drop}%</div>
                        </div>
                    </div>
                `);
                
                markers.push(marker);
                
                // Zoom to fault
                map.setView([result.y, result.x], 0);
                
            } catch (error) {
                console.error('❌ Fault injection error:', error);
                alert('Simulation error: ' + error);
            }
        }
        
        // ===== POPULATE BUS DROPDOWN =====
        async function populateBusDropdown() {
            try {
                const buses = await window.pywebview.api.get_bus_list();
                const select = document.getElementById('bus-select');
                
                buses.forEach(bus => {
                    const option = document.createElement('option');
                    option.value = bus;
                    option.textContent = `Bus ${bus}`;
                    select.appendChild(option);
                });
                
            } catch (error) {
                console.error('❌ Bus dropdown error:', error);
            }
        }
        
        // ===== INITIALIZATION =====
        window.addEventListener('pywebviewready', async function() {
            console.log('✓ PyWebView ready');
            
            initMap();
            await drawTopology();
            await populateBusDropdown();
            
            // Initial data fetch
            await updateFaults();
            
            // Start real-time updates (every 1 second)
            updateInterval = setInterval(updateFaults, 1000);
            
            console.log('✓ System fully initialized - Auto-refresh active');
        });
    </script>
</body>
</html>
"""


# ============================================================================
# MAIN APPLICATION
# ============================================================================

def main():
    api = Api()
    
    window = webview.create_window(
        "TACTICAL SCADA - IEEE 13 Node Test Feeder",
        html=HTML,
        js_api=api,
        width=1600,
        height=900,
        resizable=True,
        background_color='#0b0c10'
    )
    
    webview.start(debug=False)


if __name__ == "__main__":
    main()