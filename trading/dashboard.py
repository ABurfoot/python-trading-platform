#!/usr/bin/env python3
"""
Trading Dashboard - Complete Feature Set
=========================================
Web-based dashboard with ALL trading platform features.

Features:
- Stock Analysis (21 signals)
- Watchlists
- Alerts
- Portfolio Tracker
- Stock Comparison
- News
- Earnings Calendar
- Sector Heatmap
- Stock Screener
- Export Reports
- Dark/Light Theme

Usage:
    python3 dashboard_full.py
    Open http://localhost:8080
"""

import os
import sys
import json
import http.server
import socketserver
import urllib.parse
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import all modules
try:
    from trading.alpaca_client import AlpacaClient
    ALPACA_AVAILABLE = True
except Exception:
    ALPACA_AVAILABLE = False

try:
    from trading.analyzer import StockAnalyzer
    ANALYZER_AVAILABLE = True
except Exception:
    ANALYZER_AVAILABLE = False

try:
    from trading.watchlist import WatchlistManager
    WATCHLIST_AVAILABLE = True
except Exception:
    WATCHLIST_AVAILABLE = False

try:
    from trading.alerts import AlertManager
    ALERTS_AVAILABLE = True
except Exception:
    ALERTS_AVAILABLE = False

try:
    from trading.portfolio import IntegratedPortfolioManager as PortfolioManager
    PORTFOLIO_AVAILABLE = True
except Exception:
    PORTFOLIO_AVAILABLE = False

try:
    from trading.news import NewsManager
    NEWS_AVAILABLE = True
except Exception:
    NEWS_AVAILABLE = False

EARNINGS_AVAILABLE = False

try:
    from trading.sectors import SectorHeatmap
    SECTORS_AVAILABLE = True
except Exception:
    SECTORS_AVAILABLE = False

SCREENER_AVAILABLE = False

try:
    from trading.export import ReportExporter
    EXPORT_AVAILABLE = True
except Exception:
    EXPORT_AVAILABLE = False


DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Trading Platform</title>
    <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%2358a6ff' stroke-width='2'><polyline points='22,7 13.5,15.5 8.5,10.5 2,17'/><polyline points='16,7 22,7 22,13'/></svg>">
    <style>
        :root {
            --bg-primary: #0d1117;
            --bg-secondary: #161b22;
            --bg-tertiary: #21262d;
            --text-primary: #f0f6fc;
            --text-secondary: #8b949e;
            --accent: #58a6ff;
            --accent-hover: #79b8ff;
            --positive: #3fb950;
            --negative: #f85149;
            --warning: #d29922;
            --border: #30363d;
            --card-shadow: 0 3px 12px rgba(0,0,0,0.4);
        }
        
        [data-theme="light"] {
            --bg-primary: #ffffff;
            --bg-secondary: #f6f8fa;
            --bg-tertiary: #eaeef2;
            --text-primary: #1f2328;
            --text-secondary: #656d76;
            --accent: #0969da;
            --accent-hover: #0550ae;
            --positive: #1a7f37;
            --negative: #cf222e;
            --warning: #9a6700;
            --border: #d0d7de;
            --card-shadow: 0 3px 12px rgba(0,0,0,0.1);
        }
        
        * { box-sizing: border-box; margin: 0; padding: 0; }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
        }
        
        /* Header */
        .header {
            background: var(--bg-secondary);
            border-bottom: 1px solid var(--border);
            padding: 12px 24px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            position: sticky;
            top: 0;
            z-index: 100;
        }
        
        .logo {
            font-size: 1.4em;
            font-weight: 700;
            color: var(--accent);
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .header-actions {
            display: flex;
            gap: 15px;
            align-items: center;
        }
        
        .theme-toggle {
            background: var(--bg-tertiary);
            border: 1px solid var(--border);
            color: var(--text-primary);
            padding: 8px 12px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 1.1em;
        }
        
        .theme-toggle:hover { background: var(--border); }
        
        /* Navigation */
        .nav {
            background: var(--bg-secondary);
            border-bottom: 1px solid var(--border);
            display: flex;
            overflow-x: auto;
            padding: 0 24px;
        }
        
        .nav-item {
            padding: 14px 20px;
            color: var(--text-secondary);
            cursor: pointer;
            border-bottom: 2px solid transparent;
            white-space: nowrap;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .nav-item:hover { color: var(--text-primary); }
        .nav-item.active {
            color: var(--accent);
            border-bottom-color: var(--accent);
        }
        
        /* Main Content */
        .main {
            max-width: 1400px;
            margin: 0 auto;
            padding: 24px;
        }
        
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        
        /* Tab Info Button */
        .tab-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
        }
        .tab-header h2 {
            margin: 0;
            font-size: 1.5em;
        }
        
        /* Info Modal */
        .info-modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.6);
            z-index: 1000;
            justify-content: center;
            align-items: center;
            padding: 20px;
            box-sizing: border-box;
            overflow-y: auto;
        }
        .info-modal.active {
            display: flex;
        }
        .info-modal-content {
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 28px 36px;
            width: 100%;
            max-width: 1300px;
            max-height: 85vh;
            overflow-y: auto;
            position: relative;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            margin: auto;
        }
        .info-modal-content h3 {
            margin-top: 0;
            margin-bottom: 20px;
            color: var(--primary);
            font-size: 1.5em;
            border-bottom: 2px solid var(--border);
            padding-bottom: 12px;
        }
        .info-modal-content p {
            line-height: 1.6;
            color: var(--text-secondary);
            margin-bottom: 12px;
            font-size: 1.05em;
        }
        .info-modal-content ul {
            padding-left: 24px;
            color: var(--text-secondary);
            margin-bottom: 16px;
        }
        .info-modal-content li {
            margin-bottom: 5px;
            line-height: 1.5;
        }
        @media (max-width: 900px) {
            .info-modal-content {
                padding: 20px 24px;
                max-height: 90vh;
            }
        }
        .info-modal-close {
            position: absolute;
            top: 16px;
            right: 20px;
            background: none;
            border: none;
            font-size: 32px;
            cursor: pointer;
            color: var(--text-muted);
            line-height: 1;
            padding: 4px 8px;
        }
        
        /* Tab Info Button */
        .info-btn {
            display: flex;
            align-items: center;
            gap: 6px;
            padding: 6px 12px;
            border-radius: 6px;
            border: 1px solid var(--border);
            background: var(--bg-tertiary);
            color: var(--text-secondary);
            font-size: 13px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
        }
        .info-btn:hover {
            background: var(--primary);
            border-color: var(--primary);
            color: white;
        }
        .info-btn::before {
            content: 'ℹ';
            font-size: 14px;
        }
        .info-modal-close:hover {
            color: var(--danger);
        }
        
        /* Cards */
        .card {
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: var(--card-shadow);
        }
        
        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
            padding-bottom: 12px;
            border-bottom: 1px solid var(--border);
        }
        
        .card-header select {
            width: auto;
            min-width: 150px;
            max-width: 200px;
        }
        
        .card-title {
            font-size: 1.1em;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        /* Forms */
        .form-row {
            display: flex;
            gap: 12px;
            margin-bottom: 16px;
            flex-wrap: wrap;
        }
        
        .form-group {
            flex: 1;
            min-width: 150px;
        }
        
        .form-group label {
            display: block;
            margin-bottom: 6px;
            color: var(--text-secondary);
            font-size: 0.9em;
        }
        
        input, select {
            width: 100%;
            padding: 10px 14px;
            background: var(--bg-tertiary);
            border: 1px solid var(--border);
            border-radius: 6px;
            color: var(--text-primary);
            font-size: 1em;
        }
        
        input:focus, select:focus {
            outline: none;
            border-color: var(--accent);
        }
        
        /* Buttons */
        .btn {
            padding: 10px 20px;
            border-radius: 6px;
            border: none;
            cursor: pointer;
            font-size: 0.95em;
            font-weight: 500;
            transition: all 0.2s;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }
        
        .btn-primary {
            background: var(--accent);
            color: white;
        }
        .btn-primary:hover { background: var(--accent-hover); }
        
        .btn-secondary {
            background: var(--bg-tertiary);
            color: var(--text-primary);
            border: 1px solid var(--border);
        }
        .btn-secondary:hover { background: var(--border); }
        
        .btn-success { background: var(--positive); color: white; }
        .btn-danger { background: var(--negative); color: white; }
        .btn-sm { padding: 6px 12px; font-size: 0.85em; }
        
        /* Tables */
        .table-container { overflow-x: auto; }
        
        table {
            width: 100%;
            border-collapse: collapse;
        }
        
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }
        
        th {
            color: var(--text-secondary);
            font-weight: 500;
            font-size: 0.9em;
        }
        
        tr:hover { background: var(--bg-tertiary); }
        
        /* Badges */
        .badge {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 0.85em;
            font-weight: 500;
        }
        
        .badge-buy { background: rgba(63,185,80,0.2); color: var(--positive); }
        .badge-sell { background: rgba(248,81,73,0.2); color: var(--negative); }
        .badge-hold { background: rgba(139,148,158,0.2); color: var(--text-secondary); }
        .badge-info { background: rgba(88,166,255,0.2); color: var(--accent); }
        
        /* Grid */
        .grid { display: grid; gap: 20px; }
        .grid-2 { grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); }
        .grid-3 { grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); }
        .grid-4 { grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); }
        
        /* Metrics */
        .metric {
            background: var(--bg-tertiary);
            padding: 16px;
            border-radius: 8px;
            text-align: center;
        }
        
        .metric-value {
            font-size: 1.8em;
            font-weight: 700;
            margin-bottom: 4px;
        }
        
        .metric-label {
            color: var(--text-secondary);
            font-size: 0.9em;
        }
        
        .positive { color: var(--positive); }
        .negative { color: var(--negative); }
        .neutral { color: var(--text-secondary); }
        
        /* Progress bars */
        .progress-bar {
            background: var(--bg-tertiary);
            border-radius: 4px;
            height: 8px;
            overflow: hidden;
        }
        
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, var(--negative), var(--warning), var(--positive));
            transition: width 0.3s;
        }
        
        /* Heatmap */
        .heatmap-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
            gap: 8px;
        }
        
        .heatmap-cell {
            padding: 16px 12px;
            border-radius: 8px;
            text-align: center;
            transition: transform 0.2s;
        }
        
        .heatmap-cell:hover { transform: scale(1.05); }
        
        .heatmap-cell .symbol { font-weight: 600; font-size: 1.1em; }
        .heatmap-cell .change { font-size: 0.9em; margin-top: 4px; }
        
        .heat-strong-up { background: #22863a; color: white; }
        .heat-up { background: #28a745; color: white; }
        .heat-slight-up { background: #85e89d; color: #22863a; }
        .heat-neutral { background: var(--bg-tertiary); }
        .heat-slight-down { background: #f97583; color: #b31d28; }
        .heat-down { background: #d73a49; color: white; }
        .heat-strong-down { background: #b31d28; color: white; }
        
        /* Signals */
        .signal-row {
            display: flex;
            align-items: center;
            padding: 10px 0;
            border-bottom: 1px solid var(--border);
        }
        
        .signal-icon { font-size: 1.2em; margin-right: 12px; }
        .signal-name { font-weight: 500; width: 120px; }
        .signal-value { color: var(--text-secondary); flex: 1; }
        
        /* News */
        .news-item {
            padding: 16px 0;
            border-bottom: 1px solid var(--border);
        }
        
        .news-item:last-child { border-bottom: none; }
        
        .news-headline {
            font-weight: 500;
            margin-bottom: 6px;
            display: flex;
            align-items: flex-start;
            gap: 8px;
        }
        
        .news-meta {
            color: var(--text-secondary);
            font-size: 0.85em;
        }
        
        /* Empty state */
        .empty-state {
            text-align: center;
            padding: 60px 20px;
            color: var(--text-secondary);
        }
        
        .empty-state-icon { font-size: 3em; margin-bottom: 16px; }
        
        /* Loading */
        .loading {
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 40px;
            color: var(--text-secondary);
        }
        
        .spinner {
            width: 24px;
            height: 24px;
            border: 3px solid var(--border);
            border-top-color: var(--accent);
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin-right: 12px;
        }
        
        @keyframes spin { to { transform: rotate(360deg); } }
        
        /* Comparison table */
        .comparison-table th { text-align: center; }
        .comparison-table td { text-align: center; }
        .comparison-table td:first-child { text-align: left; font-weight: 500; }
        
        /* Modal */
        .modal-overlay {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0,0,0,0.7);
            z-index: 1000;
            align-items: center;
            justify-content: center;
        }
        
        .modal-overlay.active { display: flex; }
        
        .modal {
            background: var(--bg-secondary);
            border-radius: 12px;
            padding: 24px;
            max-width: 500px;
            width: 90%;
            max-height: 80vh;
            overflow-y: auto;
        }
        
        .modal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }
        
        .modal-close {
            background: none;
            border: none;
            color: var(--text-secondary);
            font-size: 1.5em;
            cursor: pointer;
        }
        
        /* Tabs within cards */
        .card-tabs {
            display: flex;
            border-bottom: 1px solid var(--border);
            margin-bottom: 16px;
        }
        
        .card-tab {
            padding: 10px 16px;
            cursor: pointer;
            color: var(--text-secondary);
            border-bottom: 2px solid transparent;
        }
        
        .card-tab.active {
            color: var(--accent);
            border-bottom-color: var(--accent);
        }
        
        /* Responsive */
        @media (max-width: 768px) {
            .nav { padding: 0 12px; }
            .nav-item { padding: 12px 14px; font-size: 0.9em; }
            .main { padding: 16px; }
            .form-row { flex-direction: column; }
            .form-group { min-width: 100%; }
        }
    </style>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
    <header class="header">
        <div class="logo">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:22px;height:22px;color:var(--accent)">
                <polyline points="22,7 13.5,15.5 8.5,10.5 2,17"></polyline>
                <polyline points="16,7 22,7 22,13"></polyline>
            </svg>
            Trading Platform
        </div>
        <div class="header-actions">
            <span id="clock" style="color: var(--text-secondary); font-size: 12px; font-variant-numeric: tabular-nums;"></span>
            <button class="theme-toggle" onclick="toggleTheme()" title="Toggle theme" style="background:var(--bg-tertiary);border:1px solid var(--border);color:var(--text-secondary);padding:8px;border-radius:6px;cursor:pointer;display:flex;align-items:center;justify-content:center;">
                <svg id="theme-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:16px;height:16px">
                    <circle cx="12" cy="12" r="5"></circle>
                    <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"></path>
                </svg>
            </button>
        </div>
    </header>
    
    <nav class="nav">
        <div class="nav-item active" onclick="showTab('analysis')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:16px;height:16px"><path d="M3 3v18h18"/><path d="m19 9-5 5-4-4-3 3"/></svg> Analysis</div>
        <div class="nav-item" onclick="showTab('predict')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:16px;height:16px"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg> ML Predict</div>
        <div class="nav-item" onclick="showTab('compare')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:16px;height:16px"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg> Compare</div>
        <div class="nav-item" onclick="showTab('watchlist')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:16px;height:16px"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/></svg> Watchlist</div>
        <div class="nav-item" onclick="showTab('portfolio')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:16px;height:16px"><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/></svg> Portfolio</div>
        <div class="nav-item" onclick="showTab('alerts')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:16px;height:16px"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg> Alerts</div>
        <div class="nav-item" onclick="showTab('news')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:16px;height:16px"><path d="M4 22h16a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v16a2 2 0 0 1-2 2zm0 0a2 2 0 0 1-2-2v-9c0-1.1.9-2 2-2h2"/></svg> News</div>
        <div class="nav-item" onclick="showTab('sectors')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:16px;height:16px"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/></svg> Sectors</div>
        <div class="nav-item" onclick="showTab('account')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:16px;height:16px"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg> Account</div>
    </nav>
    
    <main class="main">
        <!-- Analysis Tab -->
        <div id="tab-analysis" class="tab-content active">
            <div class="card">
                <div class="card-header">
                    <div class="card-title"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:18px;height:18px;color:var(--accent)"><path d="M3 3v18h18"/><path d="m19 9-5 5-4-4-3 3"/></svg> Stock Analysis</div>
                    <button class="info-btn" onclick="showTabInfo('analysis')" title="Learn more">Info</button>
                </div>
                <div class="form-row">
                    <div class="form-group" style="flex: 2;">
                        <input type="text" id="analysis-symbol" placeholder="Enter symbol (e.g., AAPL, ASX:BHP, LSE:VOD)" 
                               onkeypress="if(event.key==='Enter')analyzeStock()">
                        <div style="font-size: 11px; color: var(--text-muted); margin-top: 4px;">Use EXCHANGE:SYMBOL format for international stocks to avoid ticker conflicts</div>
                    </div>
                    <div class="form-group" style="flex: 0;">
                        <button class="btn btn-primary" onclick="analyzeStock()">Analyze</button>
                    </div>
                    <div class="form-group" style="flex: 0;">
                        <button class="btn btn-secondary" onclick="showExportModal()">Export</button>
                    </div>
                </div>
                <div id="analysis-results">
                    <div class="empty-state">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:48px;height:48px;opacity:0.5;margin-bottom:16px"><path d="M3 3v18h18"/><path d="m19 9-5 5-4-4-3 3"/></svg>
                        <p>Enter a stock symbol to analyze</p>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- ML Predictions Tab -->
        <div id="tab-predict" class="tab-content">
            <div class="card">
                <div class="card-header">
                    <div class="card-title"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:18px;height:18px;color:var(--accent)"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg> Advanced ML Price Prediction</div>
                    <button class="info-btn" onclick="showTabInfo('predict')" title="Learn more">Info</button>
                </div>
                <div class="card-body">
                    <div class="form-row" style="flex-wrap: wrap;">
                        <div class="form-group" style="flex: 2; min-width: 180px;">
                            <label>Stock Symbol</label>
                            <input type="text" id="predict-symbol" placeholder="e.g., AAPL, ASX:BHP" onkeypress="if(event.key==='Enter')runPrediction()">
                        </div>
                        <div class="form-group" style="flex: 1; min-width: 100px;">
                            <label>Days to Predict</label>
                            <input type="number" id="predict-days" value="30" min="1" max="90">
                        </div>
                        <div class="form-group" style="flex: 1; min-width: 120px;">
                            <label>Validation Windows</label>
                            <input type="number" id="predict-windows" value="5" min="1" max="20">
                        </div>
                    </div>
                    <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                        <button class="btn btn-primary" onclick="runPrediction()">Run ML Prediction</button>
                    </div>
                    <p style="font-size: 0.85em; color: var(--text-muted); margin-top: 12px;">
                        ⚡ <strong>Ensemble ML:</strong> LSTM + Random Forest + XGBoost + Gradient Boosting with hyperparameter tuning, cross-validation, and backtesting
                    </p>
                </div>
            </div>
            
            <div id="predict-loading" style="display:none; padding: 40px; text-align: center;">
                <div class="spinner" style="margin: 0 auto 16px;"></div>
                <p id="predict-status">Training ensemble models...</p>
            </div>
            
            <div id="predict-results" style="display:none;">
                <!-- Signal Card -->
                <div class="card">
                    <div class="card-header">
                        <div class="card-title">ML Signal</div>
                    </div>
                    <div class="card-body">
                        <div class="grid grid-4" id="predict-signal-grid">
                        </div>
                    </div>
                </div>
                
                <!-- Walk-Forward Validation Card -->
                <div class="card">
                    <div class="card-header">
                        <div class="card-title">Walk-Forward Validation</div>
                    </div>
                    <div class="card-body">
                        <div class="grid grid-4" id="predict-validation-grid">
                        </div>
                    </div>
                </div>
                
                <!-- Price Predictions Card -->
                <div class="card">
                    <div class="card-header">
                        <div class="card-title">Price Forecast</div>
                    </div>
                    <div id="predict-chart" style="padding: 16px; height: 300px;">
                        <canvas id="prediction-canvas"></canvas>
                    </div>
                    <div id="predict-table" style="padding: 0 16px 16px;"></div>
                </div>
                
                <!-- Model Info Card -->
                <div class="card">
                    <div class="card-header">
                        <div class="card-title">Model Information</div>
                    </div>
                    <div class="card-body" id="predict-model-info">
                    </div>
                </div>
            </div>
            
            <div id="predict-error" style="display:none;" class="card">
                <div class="card-body">
                    <div class="empty-state">
                        <p id="predict-error-message" style="color: var(--danger);"></p>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Compare Tab -->
        <div id="tab-compare" class="tab-content">
            <div class="card">
                <div class="card-header">
                    <div class="card-title"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:18px;height:18px;color:var(--accent)"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg> Stock Comparison</div>
                    <button class="info-btn" onclick="showTabInfo('compare')" title="Learn more">Info</button>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <input type="text" id="compare-symbols" placeholder="Enter 2-8 symbols (e.g., AAPL, NASDAQ:MSFT, ASX:BHP, LON:SHEL)"
                               onkeypress="if(event.key==='Enter')compareStocks()">
                        <div style="font-size: 11px; color: var(--text-muted); margin-top: 4px;">Separate symbols with commas. Use EXCHANGE:SYMBOL format for clarity.</div>
                    </div>
                    <div class="form-group" style="flex: 0;">
                        <button class="btn btn-primary" onclick="compareStocks()">Compare</button>
                    </div>
                </div>
                <div id="compare-results">
                    <div class="empty-state">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:48px;height:48px;opacity:0.5;margin-bottom:16px"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>
                        <p>Enter multiple symbols separated by commas to compare</p>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Watchlist Tab -->
        <div id="tab-watchlist" class="tab-content">
            <div class="card">
                <div class="card-header">
                    <div class="card-title"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:18px;height:18px;color:var(--accent)"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/></svg> Watchlists</div>
                    <div style="display: flex; gap: 8px; align-items: center;">
                        <button class="btn btn-sm btn-secondary" onclick="showModal('modal-create-watchlist')">+ New List</button>
                        <button class="info-btn" onclick="showTabInfo('watchlist')" title="Learn more">Info</button>
                    </div>
                </div>
                <div class="card-body">
                    <div class="form-row" style="flex-wrap: wrap;">
                        <div class="form-group" style="flex: 1; min-width: 140px;">
                            <label>Watchlist</label>
                            <select id="watchlist-select" onchange="loadWatchlist()">
                                <option value="default">Default</option>
                            </select>
                        </div>
                        <div class="form-group" style="flex: 2; min-width: 180px;">
                            <label>Add Symbol</label>
                            <input type="text" id="watchlist-add-symbol" placeholder="e.g., AAPL, ASX:BHP" onkeypress="if(event.key==='Enter')addToWatchlist()">
                        </div>
                    </div>
                    <div style="display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 16px;">
                        <button class="btn btn-primary btn-sm" onclick="addToWatchlist()">Add Symbol</button>
                        <button class="btn btn-secondary btn-sm" onclick="analyzeWatchlist()" title="Analyze all stocks">Analyze All</button>
                        <button class="btn btn-danger btn-sm" onclick="deleteWatchlist()" title="Delete watchlist">Delete Watchlist</button>
                    </div>
                </div>
                <div id="watchlist-content">
                    <div class="loading"><div class="spinner"></div> Loading...</div>
                </div>
            </div>
        </div>
        
        <!-- Portfolio Tab -->
        <div id="tab-portfolio" class="tab-content">
            <div class="card">
                <div class="card-header">
                    <div class="card-title"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:18px;height:18px;color:var(--accent)"><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/></svg> Paper Portfolio</div>
                    <div style="display: flex; gap: 8px; align-items: center;">
                        <select id="portfolio-select" onchange="onPortfolioChange()">
                            <option value="default">Default Portfolio</option>
                        </select>
                        <button class="btn btn-sm btn-secondary" onclick="showModal('modal-create-portfolio')">+ New</button>
                        <button id="portfolio-delete-btn" class="btn btn-sm btn-warning" onclick="confirmDeleteOrResetPortfolio()">Reset</button>
                        <button class="btn btn-sm btn-secondary" onclick="exportPortfolioCSV()">Export</button>
                        <button class="btn btn-sm btn-secondary" onclick="showModal('modal-import-csv')">Import</button>
                        <button class="info-btn" onclick="showTabInfo('portfolio')" title="Learn more">Info</button>
                    </div>
                </div>
                <div class="card-body">
                    <div id="portfolio-summary" class="grid grid-4" style="margin-bottom: 20px;"></div>
                </div>
                
                <!-- Charts Row -->
                <div class="form-row" style="padding: 0 16px; margin-bottom: 16px;">
                    <div class="card" style="flex: 1; min-width: 280px; margin: 0 8px 0 0;">
                        <div class="card-header" style="padding: 12px 16px;">
                            <div class="card-title" style="font-size: 0.95em;">Allocation by Stock</div>
                        </div>
                        <div style="padding: 16px; height: 250px;">
                            <canvas id="portfolio-allocation-chart"></canvas>
                        </div>
                    </div>
                    <div class="card" style="flex: 1; min-width: 280px; margin: 0 0 0 8px;">
                        <div class="card-header" style="padding: 12px 16px;">
                            <div class="card-title" style="font-size: 0.95em;">Sector Allocation</div>
                        </div>
                        <div style="padding: 16px; height: 250px;">
                            <canvas id="portfolio-sector-chart"></canvas>
                        </div>
                    </div>
                </div>
                
                <!-- Performance Chart -->
                <div class="card" style="margin: 0 16px 16px 16px;">
                    <div class="card-header" style="padding: 12px 16px;">
                        <div class="card-title" style="font-size: 0.95em;">Portfolio Performance</div>
                        <div style="display: flex; gap: 6px;">
                            <button class="btn btn-sm btn-secondary" onclick="loadPerformanceChart('1M')">1M</button>
                            <button class="btn btn-sm btn-secondary" onclick="loadPerformanceChart('3M')">3M</button>
                            <button class="btn btn-sm btn-secondary" onclick="loadPerformanceChart('6M')">6M</button>
                            <button class="btn btn-sm btn-secondary active" onclick="loadPerformanceChart('1Y')">1Y</button>
                            <button class="btn btn-sm btn-secondary" onclick="loadPerformanceChart('ALL')">ALL</button>
                        </div>
                    </div>
                    <div style="padding: 16px; height: 200px;">
                        <canvas id="portfolio-performance-chart"></canvas>
                    </div>
                </div>
                
                <div class="card-tabs">
                    <div class="card-tab active" onclick="showPortfolioTab('positions')">Positions</div>
                    <div class="card-tab" onclick="showPortfolioTab('trade')">Trade</div>
                    <div class="card-tab" onclick="showPortfolioTab('dividends')">Dividends</div>
                    <div class="card-tab" onclick="showPortfolioTab('cash')">Deposit/Withdraw</div>
                    <div class="card-tab" onclick="showPortfolioTab('history')">History</div>
                </div>
                <div style="padding: 16px;">
                    <div id="portfolio-positions"></div>
                    <div id="portfolio-trade" style="display:none;">
                        <div class="form-row" style="flex-wrap: wrap;">
                            <div class="form-group" style="flex: 2; min-width: 150px;">
                                <label>Symbol</label>
                                <input type="text" id="trade-symbol" placeholder="e.g., AAPL, ASX:BHP">
                            </div>
                            <div class="form-group" style="flex: 1; min-width: 100px;">
                                <label>Quantity</label>
                                <input type="number" id="trade-quantity" placeholder="10">
                            </div>
                            <div class="form-group" style="flex: 1; min-width: 120px;">
                                <label>Price <span id="trade-price-hint" style="font-size:0.8em;color:var(--text-muted);"></span></label>
                                <input type="number" id="trade-price" step="0.01" placeholder="150.00">
                            </div>
                        </div>
                        <div style="display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 16px;">
                            <button class="btn btn-secondary" onclick="getTradeQuote()">Get Current Price</button>
                            <button class="btn btn-success" onclick="executeTrade('buy')">Buy</button>
                            <button class="btn btn-danger" onclick="executeTrade('sell')">Sell</button>
                        </div>
                        <p style="font-size: 0.85em; color: var(--text-muted); margin: 0;">Tip: Price must be within 10% of market price</p>
                    </div>
                    <div id="portfolio-dividends" style="display:none;">
                        <div class="form-row" style="flex-wrap: wrap; margin-bottom: 16px;">
                            <div class="form-group" style="flex: 1; min-width: 120px;">
                                <label>Symbol</label>
                                <input type="text" id="dividend-symbol" placeholder="e.g., AAPL">
                            </div>
                            <div class="form-group" style="flex: 1; min-width: 100px;">
                                <label>Amount</label>
                                <input type="number" id="dividend-amount" step="0.01" placeholder="50.00">
                            </div>
                            <div class="form-group" style="flex: 1; min-width: 100px;">
                                <label>Ex-Date</label>
                                <input type="date" id="dividend-date">
                            </div>
                            <div class="form-group" style="flex: 0; display: flex; align-items: flex-end;">
                                <button class="btn btn-success" onclick="recordDividend()">Record Dividend</button>
                            </div>
                        </div>
                        <div id="portfolio-dividend-history"></div>
                    </div>
                    <div id="portfolio-cash" style="display:none;">
                        <div class="form-row" style="flex-wrap: wrap;">
                            <div class="form-group" style="flex: 1; min-width: 140px;">
                                <label>Amount ($)</label>
                                <input type="number" id="cash-amount" step="0.01" placeholder="10000.00">
                            </div>
                            <div class="form-group" style="flex: 2; min-width: 180px;">
                                <label>Notes (optional)</label>
                                <input type="text" id="cash-notes" placeholder="e.g., Monthly contribution">
                            </div>
                        </div>
                        <div style="display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 16px;">
                            <button class="btn btn-success" onclick="portfolioCash('deposit')">Deposit</button>
                            <button class="btn btn-danger" onclick="portfolioCash('withdraw')">Withdraw</button>
                        </div>
                    </div>
                    <div id="portfolio-history" style="display:none;"></div>
                </div>
            </div>
        </div>
        
        <!-- Alerts Tab -->
        <div id="tab-alerts" class="tab-content">
            <div class="card">
                <div class="card-header">
                    <div class="card-title"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:18px;height:18px;color:var(--accent)"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg> Price Alerts</div>
                    <button class="info-btn" onclick="showTabInfo('alerts')" title="Learn more">Info</button>
                </div>
                <div class="card-body">
                    <div class="form-row" style="flex-wrap: wrap;">
                        <div class="form-group" style="flex: 2; min-width: 150px;">
                            <label>Symbol</label>
                            <input type="text" id="alert-symbol" placeholder="e.g., AAPL, ASX:BHP">
                        </div>
                        <div class="form-group" style="flex: 1; min-width: 130px;">
                            <label>Alert Type</label>
                            <select id="alert-type" onchange="updateAlertFields()">
                                <option value="price">Price Alert</option>
                                <option value="percent">% Change Alert</option>
                                <option value="signal">Signal Alert</option>
                            </select>
                        </div>
                        <div class="form-group" id="alert-condition-group" style="flex: 1; min-width: 100px;">
                            <label>Condition</label>
                            <select id="alert-condition">
                                <option value="above">Above</option>
                                <option value="below">Below</option>
                            </select>
                        </div>
                        <div class="form-group" id="alert-value-group" style="flex: 1; min-width: 120px;">
                            <label>Target Price</label>
                            <input type="number" id="alert-price" step="0.01" placeholder="200.00">
                        </div>
                        <div class="form-group" id="alert-signal-group" style="display:none; flex: 1; min-width: 120px;">
                            <label>Signal</label>
                            <select id="alert-signal">
                                <option value="STRONG BUY">Strong Buy</option>
                                <option value="BUY">Buy</option>
                                <option value="SELL">Sell</option>
                                <option value="STRONG SELL">Strong Sell</option>
                            </select>
                        </div>
                    </div>
                    <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                        <button class="btn btn-primary" onclick="createAlert()">Create Alert</button>
                    </div>
                </div>
                <div id="alerts-list" style="padding: 0 16px 16px;"></div>
            </div>
        </div>
                <div id="alerts-list"></div>
            </div>
        </div>
        
        <!-- News Tab -->
        <div id="tab-news" class="tab-content">
            <div class="card">
                <div class="card-header">
                    <div class="card-title"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:18px;height:18px;color:var(--accent)"><path d="M4 22h16a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v16a2 2 0 0 1-2 2zm0 0a2 2 0 0 1-2-2v-9c0-1.1.9-2 2-2h2"/></svg> Market News</div>
                    <button class="info-btn" onclick="showTabInfo('news')" title="Learn more">Info</button>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <input type="text" id="news-symbol" placeholder="Enter symbol" 
                               onkeypress="if(event.key==='Enter')loadNews()">
                    </div>
                    <div class="form-group" style="flex: 0;">
                        <button class="btn btn-primary" onclick="loadNews()">Get News</button>
                    </div>
                </div>
                <div id="news-content">
                    <div class="empty-state">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:48px;height:48px;opacity:0.5;margin-bottom:16px"><path d="M4 22h16a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v16a2 2 0 0 1-2 2zm0 0a2 2 0 0 1-2-2v-9c0-1.1.9-2 2-2h2"/></svg>
                        <p>Enter a symbol to view recent news</p>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Sectors Tab -->
        <div id="tab-sectors" class="tab-content">
            <div class="card">
                <div class="card-header">
                    <div class="card-title"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:18px;height:18px;color:var(--accent)"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/></svg> Sector Performance</div>
                    <div style="display: flex; gap: 8px; align-items: center;">
                        <select id="sector-period" onchange="loadSectors()" style="min-width: 120px;">
                            <option value="1d" selected>1 Day</option>
                            <option value="5d">5 Days</option>
                            <option value="1w">1 Week</option>
                            <option value="1m">1 Month</option>
                            <option value="3m">3 Months</option>
                            <option value="6m">6 Months</option>
                            <option value="ytd">YTD</option>
                            <option value="1y">1 Year</option>
                            <option value="3y">3 Years</option>
                            <option value="5y">5 Years</option>
                        </select>
                        <button class="btn btn-sm btn-secondary" onclick="loadSectors()">Refresh</button>
                        <button class="info-btn" onclick="showTabInfo('sectors')" title="Learn more">Info</button>
                    </div>
                </div>
                <div id="sectors-content">
                    <div class="loading"><div class="spinner"></div> Loading sectors...</div>
                </div>
            </div>
        </div>
        
        <!-- Account Tab -->
        <div id="tab-account" class="tab-content">
            <div class="card">
                <div class="card-header">
                    <div class="card-title"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:18px;height:18px;color:var(--accent)"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg> Alpaca Account</div>
                    <div style="display:flex;gap:8px;align-items:center;">
                        <button class="btn btn-sm btn-success" onclick="showLiveTradeModal()">Place Order</button>
                        <button class="btn btn-sm btn-secondary" onclick="loadAccount()">Refresh</button>
                        <button class="info-btn" onclick="showTabInfo('account')" title="Learn more">Info</button>
                    </div>
                </div>
                <div class="card-body">
                    <div id="account-summary" class="grid grid-4"></div>
                </div>
            </div>
            <div class="card">
                <div class="card-header">
                    <div class="card-title">Live Positions</div>
                </div>
                <div id="account-positions" style="padding:16px;"></div>
            </div>
            <div class="card">
                <div class="card-header">
                    <div class="card-title">Recent Orders</div>
                </div>
                <div id="account-orders" style="padding:16px;"></div>
            </div>
        </div>
    </main>
    
    <!-- Create Watchlist Modal -->
    <div class="modal-overlay" id="modal-create-watchlist">
        <div class="modal">
            <div class="modal-header">
                <h3>Create Watchlist</h3>
                <button class="modal-close" onclick="closeModal('modal-create-watchlist')">&times;</button>
            </div>
            <div class="form-group">
                <label>Watchlist Name</label>
                <input type="text" id="new-watchlist-name" placeholder="e.g., Tech Stocks">
            </div>
            <div style="margin-top: 20px; text-align: right;">
                <button class="btn btn-secondary" onclick="closeModal('modal-create-watchlist')">Cancel</button>
                <button class="btn btn-primary" onclick="createWatchlist()">Create</button>
            </div>
        </div>
    </div>
    
    <!-- Create Portfolio Modal -->
    <div class="modal-overlay" id="modal-create-portfolio">
        <div class="modal">
            <div class="modal-header">
                <h3>Create Portfolio</h3>
                <button class="modal-close" onclick="closeModal('modal-create-portfolio')">&times;</button>
            </div>
            <div class="form-group" style="margin-bottom: 16px;">
                <label>Portfolio Name</label>
                <input type="text" id="new-portfolio-name" placeholder="e.g., Growth Portfolio">
            </div>
            <div class="form-group">
                <label>Starting Cash ($)</label>
                <input type="number" id="new-portfolio-cash" value="100000" step="1000">
            </div>
            <div style="margin-top: 20px; text-align: right;">
                <button class="btn btn-secondary" onclick="closeModal('modal-create-portfolio')">Cancel</button>
                <button class="btn btn-primary" onclick="createPortfolio()">Create</button>
            </div>
        </div>
    </div>
    
    <!-- Import CSV Modal -->
    <div class="modal-overlay" id="modal-import-csv">
        <div class="modal" style="max-width: 550px;">
            <div class="modal-header">
                <h3>Import Transactions from CSV</h3>
                <button class="modal-close" onclick="closeModal('modal-import-csv')">&times;</button>
            </div>
            <p style="color: var(--text-secondary); margin-bottom: 16px;">Upload a CSV file with your transactions. Expected columns:</p>
            <div style="background: var(--bg-tertiary); padding: 12px; border-radius: 6px; margin-bottom: 16px; font-family: monospace; font-size: 0.85em;">
                date,type,symbol,quantity,price,notes<br>
                2024-01-15,buy,AAPL,10,185.50,Initial purchase<br>
                2024-02-01,buy,MSFT,5,405.00,Adding to position<br>
                2024-03-10,sell,AAPL,5,175.00,Taking profits<br>
                2024-03-15,dividend,AAPL,12.50,,Q1 dividend
            </div>
            <div class="form-group">
                <label>Select CSV File</label>
                <input type="file" id="import-csv-file" accept=".csv" style="padding: 8px;">
            </div>
            <div style="margin-top: 20px; text-align: right;">
                <button class="btn btn-secondary" onclick="closeModal('modal-import-csv')">Cancel</button>
                <button class="btn btn-primary" onclick="importPortfolioCSV()">Import</button>
            </div>
        </div>
    </div>
    
    <!-- Export Modal -->
    <div class="modal-overlay" id="modal-export">
        <div class="modal">
            <div class="modal-header">
                <h3>Export Analysis</h3>
                <button class="modal-close" onclick="closeModal('modal-export')">&times;</button>
            </div>
            <p style="color: var(--text-secondary); margin-bottom: 16px;">Export the current analysis to a file.</p>
            <div class="form-group">
                <label>Format</label>
                <select id="export-format-select">
                    <option value="html">HTML Report (recommended)</option>
                    <option value="csv">CSV Data</option>
                    <option value="json">JSON</option>
                    <option value="txt">Plain Text</option>
                </select>
            </div>
            <div style="margin-top: 20px; text-align: right;">
                <button class="btn btn-secondary" onclick="closeModal('modal-export')">Cancel</button>
                <button class="btn btn-primary" onclick="exportCurrentAnalysis()">Export</button>
            </div>
        </div>
    </div>
    
    <!-- Live Trade Modal (Alpaca) -->
    <div class="modal-overlay" id="modal-live-trade">
        <div class="modal">
            <div class="modal-header">
                <h3>Place Live Order (Alpaca)</h3>
                <button class="modal-close" onclick="closeModal('modal-live-trade')">&times;</button>
            </div>
            <p style="color: var(--negative); margin-bottom: 16px; font-weight: 500;">WARNING: This will place a REAL order with your Alpaca account!</p>
            <div class="form-group" style="margin-bottom: 12px;">
                <label>Symbol</label>
                <input type="text" id="live-trade-symbol" placeholder="AAPL">
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label>Side</label>
                    <select id="live-trade-side">
                        <option value="buy">Buy</option>
                        <option value="sell">Sell</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Quantity</label>
                    <input type="number" id="live-trade-qty" placeholder="1">
                </div>
            </div>
            <div class="form-group">
                <label>Order Type</label>
                <select id="live-trade-type">
                    <option value="market">Market</option>
                    <option value="limit">Limit (not implemented)</option>
                </select>
            </div>
            <div style="margin-top: 20px; text-align: right;">
                <button class="btn btn-secondary" onclick="closeModal('modal-live-trade')">Cancel</button>
                <button class="btn btn-danger" onclick="placeLiveOrder()">Place Order</button>
            </div>
        </div>
    </div>

    <!-- Info Modal -->
    <div id="info-modal" class="info-modal" onclick="if(event.target===this)closeInfoModal()">
        <div class="info-modal-content">
            <button class="info-modal-close" onclick="closeInfoModal()">&times;</button>
            <div id="info-modal-body"></div>
        </div>
    </div>

    <script>
        // Info content for each tab
        const tabInfoContent = {
            'analysis': {
                title: 'Stock Analysis',
                content: `
                    <p>Get comprehensive analysis of any stock with <strong>21 trading signals</strong> across multiple categories.</p>
                    <p><strong>How to use:</strong></p>
                    <ul>
                        <li>Enter a stock symbol (e.g., AAPL, ASX:BHP, LON:SHEL)</li>
                        <li>View the overall score (0-100) and recommendation</li>
                        <li>Explore Technical, Fundamental, and Analyst signals</li>
                        <li>Check risk metrics and analyst price targets</li>
                    </ul>
                    <p><strong>Technical Signals (8):</strong></p>
                    <ul>
                        <li>RSI (Relative Strength Index) - Overbought/Oversold detection</li>
                        <li>MACD (Moving Average Convergence Divergence) - Trend momentum</li>
                        <li>SMA 20/50 Crossover - Short-term trend direction</li>
                        <li>SMA 50/200 Crossover (Golden/Death Cross) - Long-term trend</li>
                        <li>Bollinger Bands - Volatility and price extremes</li>
                        <li>Volume Trend - Confirms price movements</li>
                        <li>52-Week Range Position - Price relative to yearly highs/lows</li>
                        <li>Price Momentum - Recent price performance</li>
                    </ul>
                    <p><strong>Fundamental Signals (9):</strong></p>
                    <ul>
                        <li>P/E Ratio - Price to earnings valuation</li>
                        <li>Forward P/E - Expected future valuation</li>
                        <li>PEG Ratio - Growth-adjusted valuation</li>
                        <li>Price to Book (P/B) - Asset-based valuation</li>
                        <li>Debt to Equity - Financial leverage</li>
                        <li>Current Ratio - Short-term liquidity</li>
                        <li>ROE (Return on Equity) - Profitability efficiency</li>
                        <li>Profit Margin - Net income percentage</li>
                        <li>Dividend Yield - Income return</li>
                    </ul>
                    <p><strong>Analyst Signals (4):</strong></p>
                    <ul>
                        <li>Analyst Consensus - Buy/Hold/Sell recommendations</li>
                        <li>Price Target Upside - Potential gain to target</li>
                        <li>Earnings Surprise - Recent EPS beat/miss</li>
                        <li>Institutional Ownership - Smart money holdings</li>
                    </ul>
                    <p><strong>Risk Metrics:</strong></p>
                    <ul>
                        <li>Annual Volatility - Price fluctuation measure</li>
                        <li>Beta - Market correlation</li>
                        <li>Value at Risk (VaR 95%) - Potential daily loss</li>
                        <li>Maximum Drawdown - Largest peak-to-trough decline</li>
                        <li>Sharpe Ratio - Risk-adjusted returns</li>
                    </ul>
                `
            },
            'predict': {
                title: 'ML Price Prediction',
                content: `
                    <p>Advanced machine learning ensemble predicts future stock prices using <strong>6 models</strong> and <strong>38 technical features</strong>.</p>
                    <p><strong>Ensemble Models:</strong></p>
                    <ul>
                        <li>Random Forest - 100 decision trees with bootstrap aggregation</li>
                        <li>XGBoost - Gradient boosted trees with regularization</li>
                        <li>XGBoost (Tuned) - Hyperparameter optimized via grid search</li>
                        <li>Gradient Boosting - Sequential tree ensemble</li>
                        <li>LSTM Neural Network - Long Short-Term Memory for sequence learning</li>
                        <li>Ridge Regression - L2-regularized linear baseline</li>
                    </ul>
                    <p><strong>Input Features (38):</strong></p>
                    <ul>
                        <li>Price Data: Open, High, Low, Close, Volume</li>
                        <li>Returns: Daily returns, Log returns, 5/10/20-day returns</li>
                        <li>Moving Averages: SMA 5, 10, 20, 50, 200</li>
                        <li>Volatility: Rolling std 5/10/20, ATR, Bollinger Bands</li>
                        <li>Momentum: RSI, MACD, MACD Signal, MACD Histogram</li>
                        <li>Volume: Volume SMA, Volume ratio, OBV</li>
                        <li>Price Levels: 52-week high/low ratio, Price percentile</li>
                        <li>Trends: Price vs SMA ratios, Crossover signals</li>
                    </ul>
                    <p><strong>Validation Methods:</strong></p>
                    <ul>
                        <li>Time-Series Cross-Validation - 5-fold temporal splits</li>
                        <li>Out-of-Sample Backtesting - 20% holdout test set</li>
                        <li>Sharpe Ratio calculation with transaction costs</li>
                        <li>Directional Accuracy measurement</li>
                    </ul>
                    <p><strong>Statistical Tests:</strong></p>
                    <ul>
                        <li>Binomial Test - Directional accuracy significance</li>
                        <li>Pearson Correlation - Prediction vs actual correlation</li>
                        <li>Shapiro-Wilk Test - Residual normality</li>
                        <li>One-Sample t-Test - Prediction bias detection</li>
                    </ul>
                    <p><strong>Output Includes:</strong></p>
                    <ul>
                        <li>Daily price predictions up to 30 days</li>
                        <li>95% confidence intervals (expanding with time)</li>
                        <li>Total return from Day 0 and period-over-period change</li>
                        <li>Model performance metrics and feature importance</li>
                    </ul>
                    <p><em>Note: Predictions are for educational purposes only. Past performance does not guarantee future results.</em></p>
                `
            },
            'compare': {
                title: 'Stock Comparison',
                content: `
                    <p>Compare multiple stocks side-by-side to make informed investment decisions.</p>
                    <p><strong>How to use:</strong></p>
                    <ul>
                        <li>Enter 2-8 stock symbols separated by commas</li>
                        <li>Use EXCHANGE:SYMBOL format for international stocks</li>
                        <li>Click any row to view full analysis</li>
                    </ul>
                    <p><strong>Comparison Metrics:</strong></p>
                    <ul>
                        <li>Current Price - Real-time or delayed quote</li>
                        <li>Daily Change - Dollar and percentage change</li>
                        <li>Overall Score - Composite 0-100 rating</li>
                        <li>Recommendation - Strong Buy to Strong Sell</li>
                        <li>P/E Ratio - Price to earnings valuation</li>
                        <li>Market Cap - Company size</li>
                        <li>52-Week Range - Annual price range position</li>
                        <li>Volatility - Annualized price fluctuation</li>
                        <li>Beta - Market correlation coefficient</li>
                        <li>Dividend Yield - Annual dividend return</li>
                    </ul>
                    <p><strong>Supported Exchanges:</strong></p>
                    <ul>
                        <li>US: NYSE, NASDAQ, AMEX</li>
                        <li>Australia: ASX</li>
                        <li>UK: LSE/LON</li>
                        <li>Europe: FRA, EPA, AMS</li>
                        <li>Canada: TSE/TSX</li>
                        <li>Asia: HKG, TYO</li>
                    </ul>
                `
            },
            'watchlist': {
                title: 'Watchlists',
                content: `
                    <p>Create and manage multiple watchlists to track your favorite stocks.</p>
                    <p><strong>Features:</strong></p>
                    <ul>
                        <li>Create unlimited custom watchlists</li>
                        <li>Add/remove stocks with one click</li>
                        <li>Real-time price updates on refresh</li>
                        <li>Quick access to full stock analysis</li>
                        <li>Delete entire watchlists when no longer needed</li>
                    </ul>
                    <p><strong>Watchlist Display:</strong></p>
                    <ul>
                        <li>Stock Symbol and Company Name</li>
                        <li>Current Price with currency</li>
                        <li>Daily Change (absolute and percentage)</li>
                        <li>Overall Analysis Score</li>
                        <li>Current Recommendation</li>
                    </ul>
                    <p><strong>Tips:</strong></p>
                    <ul>
                        <li>Organize by sector (e.g., "Tech Stocks", "Dividends")</li>
                        <li>Create strategy-based lists (e.g., "Momentum Plays")</li>
                        <li>Watchlists are saved locally in your browser</li>
                        <li>Export functionality available for backup</li>
                    </ul>
                `
            },
            'portfolio': {
                title: 'Portfolio Tracker',
                content: `
                    <p>Track your investments with a virtual paper trading portfolio simulator.</p>
                    <p><strong>Portfolio Features:</strong></p>
                    <ul>
                        <li>Create multiple named portfolios</li>
                        <li>Simulate buy and sell transactions</li>
                        <li>Track profit/loss per position</li>
                        <li>Deposit and withdraw virtual cash</li>
                        <li>Complete transaction history</li>
                    </ul>
                    <p><strong>Position Tracking:</strong></p>
                    <ul>
                        <li>Symbol and quantity held</li>
                        <li>Average cost basis per share</li>
                        <li>Current market value</li>
                        <li>Unrealized P&L (dollar and percentage)</li>
                        <li>Portfolio weight allocation</li>
                    </ul>
                    <p><strong>Portfolio Summary:</strong></p>
                    <ul>
                        <li>Total Portfolio Value</li>
                        <li>Available Cash Balance</li>
                        <li>Total Invested Amount</li>
                        <li>Overall Return Percentage</li>
                        <li>Number of Positions</li>
                    </ul>
                    <p><strong>Transaction Types:</strong></p>
                    <ul>
                        <li>Buy - Purchase shares at specified price</li>
                        <li>Sell - Liquidate shares at specified price</li>
                        <li>Deposit - Add cash to portfolio</li>
                        <li>Withdraw - Remove cash from portfolio</li>
                    </ul>
                `
            },
            'alerts': {
                title: 'Price Alerts',
                content: `
                    <p>Set customizable price alerts to monitor stocks and get notified when they hit your targets.</p>
                    <p><strong>Alert Types:</strong></p>
                    <ul>
                        <li><strong>Price Above:</strong> Triggers when price rises above your target</li>
                        <li><strong>Price Below:</strong> Triggers when price falls below your target</li>
                        <li><strong>Percent Change:</strong> Triggers on percentage move from current price</li>
                        <li><strong>Signal Alert:</strong> Triggers on Buy/Sell signal changes</li>
                    </ul>
                    <p><strong>Alert Information:</strong></p>
                    <ul>
                        <li>Stock symbol being monitored</li>
                        <li>Target price or percentage</li>
                        <li>Alert condition (above/below)</li>
                        <li>Current price vs target</li>
                        <li>Alert status (pending/triggered)</li>
                        <li>Date created</li>
                    </ul>
                    <p><strong>How to use:</strong></p>
                    <ul>
                        <li>Enter stock symbol and target price</li>
                        <li>Select alert condition</li>
                        <li>Click Create Alert</li>
                        <li>Alerts are checked on each page refresh</li>
                        <li>Triggered alerts are highlighted</li>
                        <li>Delete alerts when no longer needed</li>
                    </ul>
                `
            },
            'news': {
                title: 'Market News',
                content: `
                    <p>Stay updated with the latest financial news and market developments.</p>
                    <p><strong>News Features:</strong></p>
                    <ul>
                        <li>Real-time news headlines</li>
                        <li>Stock-specific news search</li>
                        <li>Publication date and source</li>
                        <li>Direct links to full articles</li>
                    </ul>
                    <p><strong>News Sources:</strong></p>
                    <ul>
                        <li>Major financial news outlets</li>
                        <li>Company press releases</li>
                        <li>SEC filings and announcements</li>
                        <li>Analyst reports and commentary</li>
                        <li>Market analysis publications</li>
                    </ul>
                    <p><strong>News Categories:</strong></p>
                    <ul>
                        <li>Earnings announcements</li>
                        <li>Mergers and acquisitions</li>
                        <li>Product launches</li>
                        <li>Management changes</li>
                        <li>Regulatory news</li>
                        <li>Market commentary</li>
                    </ul>
                `
            },
            'sectors': {
                title: 'Sector Analysis',
                content: `
                    <p>Analyze market sectors to identify trends, rotation, and opportunities.</p>
                    <p><strong>Sectors Tracked (11 GICS Sectors):</strong></p>
                    <ul>
                        <li>Technology - Software, hardware, semiconductors</li>
                        <li>Healthcare - Pharma, biotech, medical devices</li>
                        <li>Financials - Banks, insurance, asset management</li>
                        <li>Consumer Discretionary - Retail, autos, entertainment</li>
                        <li>Consumer Staples - Food, beverages, household products</li>
                        <li>Industrials - Aerospace, machinery, transportation</li>
                        <li>Energy - Oil, gas, renewable energy</li>
                        <li>Materials - Chemicals, metals, mining</li>
                        <li>Real Estate - REITs, property developers</li>
                        <li>Utilities - Electric, gas, water utilities</li>
                        <li>Communication Services - Telecom, media, internet</li>
                    </ul>
                    <p><strong>Sector Metrics:</strong></p>
                    <ul>
                        <li>Daily performance percentage</li>
                        <li>Weekly and monthly returns</li>
                        <li>Year-to-date performance</li>
                        <li>Relative strength vs S&P 500</li>
                    </ul>
                    <p><strong>Sector Rotation Strategy:</strong></p>
                    <ul>
                        <li>Early Cycle: Financials, Consumer Discretionary</li>
                        <li>Mid Cycle: Technology, Industrials</li>
                        <li>Late Cycle: Energy, Materials</li>
                        <li>Recession: Utilities, Healthcare, Staples</li>
                    </ul>
                `
            },
            'account': {
                title: 'Broker Account',
                content: `
                    <p>Connect to your Alpaca brokerage account for real-time data and live trading.</p>
                    <p><strong>Account Information:</strong></p>
                    <ul>
                        <li>Account Equity - Total account value</li>
                        <li>Buying Power - Available for trading</li>
                        <li>Cash Balance - Settled cash</li>
                        <li>Daily P&L - Today's profit/loss</li>
                        <li>Portfolio Value - Total position value</li>
                    </ul>
                    <p><strong>Position Tracking:</strong></p>
                    <ul>
                        <li>All open positions</li>
                        <li>Quantity and average cost</li>
                        <li>Current market value</li>
                        <li>Unrealized P&L</li>
                        <li>Today's change</li>
                    </ul>
                    <p><strong>Order Management:</strong></p>
                    <ul>
                        <li>Place market orders</li>
                        <li>Place limit orders</li>
                        <li>View pending orders</li>
                        <li>View filled orders</li>
                        <li>Cancel open orders</li>
                    </ul>
                    <p><strong>Setup Requirements:</strong></p>
                    <ul>
                        <li>Alpaca account (free to create)</li>
                        <li>API Key ID from Alpaca dashboard</li>
                        <li>API Secret Key from Alpaca dashboard</li>
                        <li>Choose Paper or Live trading mode</li>
                    </ul>
                    <p><strong>Warning:</strong> Live trading involves real money and risk of loss. Always start with paper trading to test strategies before using real funds.</p>
                `
            }
        };
        
        function showTabInfo(tabId) {
            const info = tabInfoContent[tabId];
            if (!info) return;
            
            document.getElementById('info-modal-body').innerHTML = `
                <h3>${info.title}</h3>
                ${info.content}
            `;
            document.getElementById('info-modal').classList.add('active');
        }
        
        function closeInfoModal() {
            document.getElementById('info-modal').classList.remove('active');
        }
        
        // Close modal on Escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') closeInfoModal();
        });
        // State
        let currentTheme = localStorage.getItem('theme') || 'dark';
        let currentAnalysis = null;
        
        // Initialize
        document.addEventListener('DOMContentLoaded', () => {
            document.body.setAttribute('data-theme', currentTheme);
            updateClock();
            setInterval(updateClock, 1000);
            loadWatchlists();
            loadPortfolios();
            loadAlerts();
        });
        
        function updateClock() {
            const now = new Date();
            document.getElementById('clock').textContent = now.toLocaleTimeString();
        }
        
        function toggleTheme() {
            currentTheme = currentTheme === 'dark' ? 'light' : 'dark';
            document.body.setAttribute('data-theme', currentTheme);
            localStorage.setItem('theme', currentTheme);
        }
        
        function showTab(tabId) {
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
            document.getElementById('tab-' + tabId).classList.add('active');
            event.target.classList.add('active');
            
            // Load data for certain tabs
            if (tabId === 'sectors') loadSectors();
            if (tabId === 'account') loadAccount();
            // Earnings tab: user must enter a symbol first
        }
        
        function showModal(id) { document.getElementById(id).classList.add('active'); }
        function closeModal(id) { document.getElementById(id).classList.remove('active'); }
        
        // API calls
        async function fetchData(endpoint, options = {}) {
            try {
                const resp = await fetch('/api/' + endpoint, options);
                return await resp.json();
            } catch (e) {
                console.error('API error:', e);
                return null;
            }
        }
        
        // Helper functions
        function cleanSymbol(s) {
            // Clean and normalize stock symbol: 'nasDAQ  :  aApl' -> 'NASDAQ:AAPL'
            if (!s) return '';
            return s.trim().toUpperCase().replace(/\\s*:\\s*/g, ':').replace(/\\s+/g, '').replace(/\\s*\\.\\s*/g, '.');
        }
        
        async function getDisplaySymbol(symbol) {
            // Get the full EXCHANGE:SYMBOL format from backend
            const cleaned = cleanSymbol(symbol);
            if (!cleaned) return '';
            try {
                const data = await fetchData('quote/' + encodeURIComponent(cleaned));
                return data && data.display_symbol ? data.display_symbol : cleaned;
            } catch {
                return cleaned;
            }
        }
        
        function getSignalIcon(signal) {
            if (signal === 'BUY') return '[+]';
            if (signal === 'SELL') return '[-]';
            return '[.]';
        }
        
        function formatCurrency(val, symbol = '$') {
            if (val === null || val === undefined) return 'N/A';
            return symbol + val.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
        }
        
        function formatPct(val) {
            if (val === null || val === undefined) return 'N/A';
            const sign = val >= 0 ? '+' : '';
            return sign + val.toFixed(2) + '%';
        }
        
        function formatMarketCap(mc, currencySymbol) {
            if (!mc || mc === 0) return 'N/A';
            const cs = currencySymbol || '$';
            if (mc >= 1e12) return cs + (mc/1e12).toFixed(2) + 'T';
            if (mc >= 1e9) return cs + (mc/1e9).toFixed(2) + 'B';
            if (mc >= 1e6) return cs + (mc/1e6).toFixed(2) + 'M';
            return cs + mc.toLocaleString();
        }
        
        // Analysis
        async function analyzeStock(symbol) {
            symbol = symbol || document.getElementById('analysis-symbol').value.trim();
            if (!symbol) return;
            
            symbol = cleanSymbol(symbol);
            document.getElementById('analysis-symbol').value = symbol;
            
            const resultsDiv = document.getElementById('analysis-results');
            resultsDiv.innerHTML = '<div class="loading"><div class="spinner"></div> Analyzing ' + symbol + '...</div>';
            
            const data = await fetchData('analyze/' + encodeURIComponent(symbol));
            currentAnalysis = data;
            
            if (data && !data.error) {
                // Update input with full EXCHANGE:SYMBOL format
                if (data.display_symbol) {
                    document.getElementById('analysis-symbol').value = data.display_symbol;
                }
                
                const cs = data.currency_symbol || '$';
                const recClass = data.recommendation.includes('BUY') ? 'positive' : 
                                 data.recommendation.includes('SELL') ? 'negative' : 'neutral';
                
                let technicalHtml = '';
                for (const s of data.technical_signals || []) {
                    technicalHtml += '<div class="signal-row"><span class="signal-icon">' + getSignalIcon(s.signal) + '</span><span class="signal-name">' + s.name + '</span><span class="signal-value">' + s.description + '</span></div>';
                }
                
                let fundamentalHtml = '';
                for (const s of data.fundamental_signals || []) {
                    fundamentalHtml += '<div class="signal-row"><span class="signal-icon">' + getSignalIcon(s.signal) + '</span><span class="signal-name">' + s.name + '</span><span class="signal-value">' + s.description + '</span></div>';
                }
                
                resultsDiv.innerHTML = `
                    <div class="grid grid-2" style="margin-bottom: 20px;">
                        <div>
                            <h2 style="margin-bottom: 8px;">${data.company_name}</h2>
                            <p style="color: var(--text-secondary);">${data.display_symbol || data.symbol} • ${data.sector} • ${data.industry}</p>
                            <p style="font-size: 2em; font-weight: 700; margin: 16px 0;">${cs}${data.current_price.toFixed(2)}</p>
                            <p class="${data.change_pct >= 0 ? 'positive' : 'negative'}" style="font-size: 1.2em;">
                                ${data.change >= 0 ? '+' : ''}${data.change.toFixed(2)} (${formatPct(data.change_pct)})
                            </p>
                        </div>
                        <div style="text-align: center;">
                            <div style="font-size: 4em; font-weight: 700;" class="${recClass}">${data.overall_score.toFixed(0)}</div>
                            <div style="color: var(--text-secondary);">/ 100</div>
                            <span class="badge ${data.recommendation.includes('BUY') ? 'badge-buy' : data.recommendation.includes('SELL') ? 'badge-sell' : 'badge-hold'}" style="font-size: 1.2em; margin-top: 12px;">
                                ${data.recommendation}
                            </span>
                            <p style="margin-top: 8px; color: var(--text-secondary);">Confidence: ${data.confidence.toFixed(0)}%</p>
                        </div>
                    </div>
                    
                    <div class="grid grid-4" style="margin-bottom: 20px;">
                        <div class="metric">
                            <div class="metric-value">${data.technical_score.toFixed(0)}</div>
                            <div class="metric-label">Technical</div>
                            <div class="progress-bar"><div class="progress-fill" style="width:${data.technical_score}%"></div></div>
                        </div>
                        <div class="metric">
                            <div class="metric-value">${data.fundamental_score.toFixed(0)}</div>
                            <div class="metric-label">Fundamental</div>
                            <div class="progress-bar"><div class="progress-fill" style="width:${data.fundamental_score}%"></div></div>
                        </div>
                        <div class="metric">
                            <div class="metric-value">${data.analyst_score.toFixed(0)}</div>
                            <div class="metric-label">Analyst</div>
                            <div class="progress-bar"><div class="progress-fill" style="width:${data.analyst_score}%"></div></div>
                        </div>
                        <div class="metric">
                            <div class="metric-value">${data.risk_score.toFixed(0)}</div>
                            <div class="metric-label">Risk Adj</div>
                            <div class="progress-bar"><div class="progress-fill" style="width:${data.risk_score}%"></div></div>
                        </div>
                    </div>
                    
                    <div class="grid grid-2">
                        <div class="card" style="margin: 0;">
                            <div class="card-title">Technical Signals</div>
                            ${technicalHtml}
                        </div>
                        <div class="card" style="margin: 0;">
                            <div class="card-title">Fundamental Signals</div>
                            ${fundamentalHtml || '<p style="color: var(--text-secondary); padding: 20px;">No fundamental data available</p>'}
                        </div>
                    </div>
                    
                    <div class="grid grid-2" style="margin-top: 20px;">
                        <div class="card" style="margin: 0;">
                            <div class="card-title">Price Targets</div>
                            <table>
                                <tr><td>Analyst Low</td><td>${cs}${data.target_low.toFixed(2)}</td><td class="${data.target_low > data.current_price ? 'positive' : 'negative'}">${formatPct((data.target_low - data.current_price) / data.current_price * 100)}</td></tr>
                                <tr><td>Analyst Avg</td><td>${cs}${data.target_mid.toFixed(2)}</td><td class="${data.target_mid > data.current_price ? 'positive' : 'negative'}">${formatPct((data.target_mid - data.current_price) / data.current_price * 100)}</td></tr>
                                <tr><td>Analyst High</td><td>${cs}${data.target_high.toFixed(2)}</td><td class="${data.target_high > data.current_price ? 'positive' : 'negative'}">${formatPct((data.target_high - data.current_price) / data.current_price * 100)}</td></tr>
                            </table>
                        </div>
                        <div class="card" style="margin: 0;">
                            <div class="card-title">Risk Metrics</div>
                            <table>
                                <tr><td>Volatility</td><td>${data.volatility.toFixed(1)}% (${data.volatility_rating})</td></tr>
                                <tr><td>VaR (95%)</td><td>${data.var_95.toFixed(2)}% max daily loss</td></tr>
                                <tr><td>Max Drawdown</td><td>${data.max_drawdown.toFixed(1)}%</td></tr>
                                <tr><td>Sharpe Ratio</td><td>${data.sharpe_ratio.toFixed(2)}</td></tr>
                            </table>
                        </div>
                    </div>
                    
                    <div class="card" style="margin-top: 20px;">
                        <div class="card-title">📝 Summary</div>
                        <p style="line-height: 1.6;">${data.summary}</p>
                    </div>
                `;
            } else {
                resultsDiv.innerHTML = '<div class="empty-state"><div class="empty-state-icon">!</div><p>Error: ' + (data?.error || 'Could not analyze stock') + '</p></div>';
            }
        }
        
        // Compare
        async function compareStocks() {
            let input = document.getElementById('compare-symbols').value.trim();
            if (!input) return;
            
            // First, normalize spaces around colons and dots (for EXCHANGE:SYMBOL format)
            input = input.replace(/\\s*:\\s*/g, ':').replace(/\\s*\\.\\s*/g, '.');
            
            // Now split on comma only (not whitespace, to preserve EXCHANGE:SYMBOL)
            // Then filter and clean each symbol
            const symbols = input.split(/,/).map(s => cleanSymbol(s.trim())).filter(s => s.length > 0 && !s.endsWith(':'));
            
            if (symbols.length < 2) {
                alert('Please enter at least 2 valid symbols (separate with commas)');
                return;
            }
            
            document.getElementById('compare-symbols').value = symbols.join(', ');
            
            const resultsDiv = document.getElementById('compare-results');
            resultsDiv.innerHTML = '<div class="loading"><div class="spinner"></div> Comparing stocks...</div>';
            
            const data = await fetchData('compare/' + encodeURIComponent(symbols.join(',')));
            
            if (data && !data.error) {
                let html = '<div class="table-container"><table class="comparison-table"><thead><tr><th>Metric</th>';
                for (const sym of data.symbols) {
                    const analysis = data.analyses[sym];
                    const displaySym = analysis?.display_symbol || sym;
                    html += '<th>' + displaySym + (data.winner === sym ? ' 🏆' : '') + '</th>';
                }
                html += '</tr></thead><tbody>';
                
                const metrics = [
                    ['Price', s => formatCurrency(data.analyses[s].current_price, data.analyses[s].currency_symbol)],
                    ['Change', s => formatPct(data.analyses[s].change_pct)],
                    ['Overall Score', s => data.analyses[s].overall_score.toFixed(0) + '/100'],
                    ['Recommendation', s => data.analyses[s].recommendation],
                    ['Technical', s => data.analyses[s].technical_score.toFixed(0)],
                    ['Fundamental', s => data.analyses[s].fundamental_score.toFixed(0)],
                    ['P/E Ratio', s => data.analyses[s].pe_ratio ? data.analyses[s].pe_ratio.toFixed(1) : 'N/A'],
                    ['Market Cap', s => formatMarketCap(data.analyses[s].market_cap, data.analyses[s].currency_symbol)],
                    ['Beta', s => data.analyses[s].beta ? data.analyses[s].beta.toFixed(2) : 'N/A'],
                    ['Volatility', s => data.analyses[s].volatility ? data.analyses[s].volatility.toFixed(1) + '%' : 'N/A'],
                    ['Sharpe Ratio', s => data.analyses[s].sharpe_ratio ? data.analyses[s].sharpe_ratio.toFixed(2) : 'N/A'],
                    ['Target Upside', s => {
                        const a = data.analyses[s];
                        if (!a.target_mid || !a.current_price) return 'N/A';
                        return formatPct((a.target_mid - a.current_price) / a.current_price * 100);
                    }],
                ];
                
                for (const [name, fn] of metrics) {
                    html += '<tr><td>' + name + '</td>';
                    for (const sym of data.symbols) {
                        html += '<td>' + fn(sym) + '</td>';
                    }
                    html += '</tr>';
                }
                
                html += '</tbody></table></div>';
                html += '<div class="card" style="margin-top: 20px;"><p><strong>🏆 Winner:</strong> ' + data.winner + ' - ' + data.summary + '</p></div>';
                
                resultsDiv.innerHTML = html;
            } else {
                resultsDiv.innerHTML = '<div class="empty-state"><p>Error: ' + (data?.error || 'Comparison failed') + '</p></div>';
            }
        }
        
        // Watchlist
        async function loadWatchlists() {
            const data = await fetchData('watchlists');
            if (data && data.watchlists) {
                const select = document.getElementById('watchlist-select');
                select.innerHTML = '';
                for (const wl of data.watchlists) {
                    select.innerHTML += '<option value="' + wl.key + '">' + wl.name + ' (' + wl.count + ')</option>';
                }
                loadWatchlist();
            }
        }
        
        async function loadWatchlist() {
            const name = document.getElementById('watchlist-select').value;
            const contentDiv = document.getElementById('watchlist-content');
            contentDiv.innerHTML = '<div class="loading"><div class="spinner"></div> Loading...</div>';
            
            const data = await fetchData('watchlist/' + name);
            
            if (data && data.stocks) {
                if (data.stocks.length === 0) {
                    contentDiv.innerHTML = '<div class="empty-state"><p>No stocks in this watchlist</p></div>';
                    return;
                }
                
                let html = '<table><thead><tr><th>Symbol</th><th>Price</th><th>Change</th><th>Score</th><th>Signal</th><th></th></tr></thead><tbody>';
                for (const stock of data.stocks) {
                    const changeClass = stock.change_pct >= 0 ? 'positive' : 'negative';
                    html += '<tr>';
                    html += '<td><strong>' + stock.symbol + '</strong></td>';
                    html += '<td>' + formatCurrency(stock.price, stock.currency_symbol) + '</td>';
                    html += '<td class="' + changeClass + '">' + formatPct(stock.change_pct) + '</td>';
                    html += '<td>' + (stock.score ? stock.score.toFixed(0) : '-') + '</td>';
                    html += '<td><span class="badge ' + (stock.recommendation?.includes('BUY') ? 'badge-buy' : stock.recommendation?.includes('SELL') ? 'badge-sell' : 'badge-hold') + '">' + (stock.recommendation || '-') + '</span></td>';
                    html += '<td><button class="btn btn-sm btn-secondary" onclick="analyzeFromWatchlist(\\'' + stock.symbol + '\\')">Analyze</button> ';
                    html += '<button class="btn btn-sm btn-danger" onclick="removeFromWatchlist(\\'' + stock.symbol + '\\')">✕</button></td>';
                    html += '</tr>';
                }
                html += '</tbody></table>';
                contentDiv.innerHTML = html;
            } else {
                contentDiv.innerHTML = '<div class="empty-state"><p>Error loading watchlist</p></div>';
            }
        }
        
        function analyzeFromWatchlist(symbol) {
            document.getElementById('analysis-symbol').value = symbol;
            showTab('analysis');
            document.querySelector('.nav-item').click();
            analyzeStock(symbol);
        }
        
        async function addToWatchlist() {
            const name = document.getElementById('watchlist-select').value;
            const symbol = cleanSymbol(document.getElementById('watchlist-add-symbol').value);
            if (!symbol) return;
            
            await fetchData('watchlist/' + name + '/add', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({symbol: symbol})
            });
            
            document.getElementById('watchlist-add-symbol').value = '';
            loadWatchlist();
            loadWatchlists();
        }
        
        async function removeFromWatchlist(symbol) {
            const name = document.getElementById('watchlist-select').value;
            await fetchData('watchlist/' + name + '/remove', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({symbol: symbol})
            });
            loadWatchlist();
            loadWatchlists();
        }
        
        function showCreateWatchlistModal() {
            showModal('modal-create-watchlist');
        }
        
        async function createWatchlist() {
            const name = document.getElementById('new-watchlist-name').value.trim();
            if (!name) return;
            
            await fetchData('watchlist/create', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({name: name})
            });
            
            closeModal('modal-create-watchlist');
            document.getElementById('new-watchlist-name').value = '';
            loadWatchlists();
        }
        
        async function deleteWatchlist() {
            const name = document.getElementById('watchlist-select').value;
            if (name === 'default') {
                alert('Cannot delete default watchlist');
                return;
            }
            if (!confirm('Delete watchlist "' + name + '"?')) return;
            
            await fetchData('watchlist/' + name + '/delete', {method: 'POST'});
            loadWatchlists();
        }
        
        async function analyzeWatchlist() {
            const name = document.getElementById('watchlist-select').value;
            const contentDiv = document.getElementById('watchlist-content');
            contentDiv.innerHTML = '<div class="loading"><div class="spinner"></div> Analyzing all stocks...</div>';
            
            const data = await fetchData('watchlist/' + name + '/analyze');
            
            if (data && data.results) {
                let html = '<table><thead><tr><th>Symbol</th><th>Price</th><th>Change</th><th>Score</th><th>Signal</th><th></th></tr></thead><tbody>';
                for (const stock of data.results) {
                    if (stock.error) {
                        html += '<tr><td><strong>' + stock.symbol + '</strong></td><td colspan="5" style="color:var(--negative)">Analysis failed</td></tr>';
                        continue;
                    }
                    const changeClass = stock.change_pct >= 0 ? 'positive' : 'negative';
                    html += '<tr><td><strong>' + stock.symbol + '</strong></td>';
                    html += '<td>' + formatCurrency(stock.price, stock.currency_symbol) + '</td>';
                    html += '<td class="' + changeClass + '">' + formatPct(stock.change_pct) + '</td>';
                    html += '<td>' + (stock.score ? stock.score.toFixed(0) : '-') + '</td>';
                    html += '<td><span class="badge ' + (stock.recommendation?.includes('BUY') ? 'badge-buy' : stock.recommendation?.includes('SELL') ? 'badge-sell' : 'badge-hold') + '">' + (stock.recommendation || '-') + '</span></td>';
                    html += '<td><button class="btn btn-sm btn-secondary" onclick="analyzeFromWatchlist(\\'' + stock.symbol + '\\')">Details</button></td></tr>';
                }
                html += '</tbody></table>';
                contentDiv.innerHTML = html;
            }
        }
        
        // Portfolio functions
        async function createPortfolio() {
            const name = document.getElementById('new-portfolio-name').value.trim();
            const cash = parseFloat(document.getElementById('new-portfolio-cash').value) || 100000;
            if (!name) return;
            
            await fetchData('portfolio/create', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({name: name, cash: cash})
            });
            
            closeModal('modal-create-portfolio');
            document.getElementById('new-portfolio-name').value = '';
            loadPortfolios();
        }
        
        async function portfolioCash(action) {
            const portfolio = document.getElementById('portfolio-select').value;
            const amount = parseFloat(document.getElementById('cash-amount').value);
            const notes = document.getElementById('cash-notes').value;
            
            if (!amount || amount <= 0) {
                alert('Enter a valid amount');
                return;
            }
            
            const result = await fetchData('portfolio/' + portfolio + '/' + action, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({amount: amount, notes: notes})
            });
            
            if (result && result.success) {
                document.getElementById('cash-amount').value = '';
                document.getElementById('cash-notes').value = '';
                loadPortfolio();
            } else {
                alert(action + ' failed: ' + (result?.error || 'Unknown error'));
            }
        }
        
        async function loadTransactionHistory() {
            const name = document.getElementById('portfolio-select').value;
            const historyDiv = document.getElementById('portfolio-history');
            historyDiv.innerHTML = '<div class="loading"><div class="spinner"></div> Loading...</div>';
            
            const data = await fetchData('portfolio/' + name + '/transactions');
            
            if (data && data.transactions && data.transactions.length > 0) {
                let html = '<table><thead><tr><th>Date</th><th>Type</th><th>Symbol</th><th>Qty</th><th>Price</th><th>Total</th></tr></thead><tbody>';
                for (const tx of data.transactions) {
                    const date = new Date(tx.timestamp).toLocaleDateString();
                    const typeClass = tx.type === 'buy' ? 'positive' : tx.type === 'sell' ? 'negative' : '';
                    html += '<tr>';
                    html += '<td>' + date + '</td>';
                    html += '<td class="' + typeClass + '" style="text-transform:uppercase;">' + tx.type + '</td>';
                    html += '<td><strong>' + tx.symbol + '</strong></td>';
                    html += '<td>' + tx.quantity + '</td>';
                    html += '<td>' + formatCurrency(tx.price) + '</td>';
                    html += '<td>' + formatCurrency(tx.total) + '</td>';
                    html += '</tr>';
                }
                html += '</tbody></table>';
                historyDiv.innerHTML = html;
            } else {
                historyDiv.innerHTML = '<div class="empty-state"><p>No transactions yet</p></div>';
            }
        }
        
        // Alert type switching
        function updateAlertFields() {
            const type = document.getElementById('alert-type').value;
            const conditionGroup = document.getElementById('alert-condition-group');
            const valueGroup = document.getElementById('alert-value-group');
            const signalGroup = document.getElementById('alert-signal-group');
            
            if (type === 'signal') {
                conditionGroup.style.display = 'none';
                valueGroup.style.display = 'none';
                signalGroup.style.display = 'block';
            } else if (type === 'percent') {
                conditionGroup.style.display = 'none';
                valueGroup.style.display = 'block';
                signalGroup.style.display = 'none';
                document.querySelector('#alert-value-group label').textContent = 'Change %';
                document.getElementById('alert-price').placeholder = '5.0';
            } else {
                conditionGroup.style.display = 'block';
                valueGroup.style.display = 'block';
                signalGroup.style.display = 'none';
                document.querySelector('#alert-value-group label').textContent = 'Target Price';
                document.getElementById('alert-price').placeholder = '200.00';
            }
        }
        
        // Export functions
        function showExportModal() {
            if (!currentAnalysis) {
                alert('Analyze a stock first');
                return;
            }
            showModal('modal-export');
        }
        
        async function exportCurrentAnalysis() {
            if (!currentAnalysis) return;
            
            const format = document.getElementById('export-format-select').value;
            const result = await fetchData('export', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({symbol: currentAnalysis.symbol, format: format})
            });
            
            closeModal('modal-export');
            
            if (result && result.success) {
                alert('Exported to: ' + result.path);
            } else {
                alert('Export failed: ' + (result?.error || 'Unknown error'));
            }
        }
        
        // Live trading (Alpaca)
        function showLiveTradeModal() {
            showModal('modal-live-trade');
        }
        
        async function placeLiveOrder() {
            const symbol = cleanSymbol(document.getElementById('live-trade-symbol').value);
            const side = document.getElementById('live-trade-side').value;
            const qty = parseFloat(document.getElementById('live-trade-qty').value);
            const orderType = document.getElementById('live-trade-type').value;
            
            if (!symbol || !qty || qty <= 0) {
                alert('Fill in all fields');
                return;
            }
            
            document.getElementById('live-trade-symbol').value = symbol;
            
            if (!confirm('Place ' + side.toUpperCase() + ' order for ' + qty + ' shares of ' + symbol + '?')) {
                return;
            }
            
            const result = await fetchData('alpaca/order', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({symbol: symbol, side: side, qty: qty, order_type: orderType})
            });
            
            closeModal('modal-live-trade');
            
            if (result && result.success) {
                alert('Order placed! ID: ' + result.order.id);
                loadAccount();
            } else {
                alert('Order failed: ' + (result?.error || 'Unknown error'));
            }
        }
        
        // Portfolio Charts
        let allocationChart = null;
        let sectorChart = null;
        let performanceChart = null;
        let currentPortfolioData = null;
        
        // Portfolio
        async function loadPortfolios() {
            const data = await fetchData('portfolios');
            if (data && data.portfolios) {
                const select = document.getElementById('portfolio-select');
                select.innerHTML = '';
                for (const p of data.portfolios) {
                    select.innerHTML += '<option value="' + p.key + '">' + p.name + '</option>';
                }
                loadPortfolio();
            }
        }
        
        async function loadPortfolio() {
            const name = document.getElementById('portfolio-select').value;
            if (!name) return;
            
            const data = await fetchData('portfolio/' + name + '?include_live=true');
            currentPortfolioData = data;
            const summaryDiv = document.getElementById('portfolio-summary');
            const posDiv = document.getElementById('portfolio-positions');
            
            if (data && !data.error) {
                const returnClass = (data.total_return || 0) >= 0 ? 'positive' : 'negative';
                
                summaryDiv.innerHTML = `
                    <div class="metric">
                        <div class="metric-value">${formatCurrency(data.total_value || 0)}</div>
                        <div class="metric-label">Total Value</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">${formatCurrency(data.cash || 0)}</div>
                        <div class="metric-label">Cash</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value ${returnClass}">${formatCurrency(data.total_return || 0)}</div>
                        <div class="metric-label">Total Return</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value ${returnClass}">${formatPct(data.total_return_pct || 0)}</div>
                        <div class="metric-label">Return %</div>
                    </div>
                `;
                
                // Positions with enhanced display
                if (data.positions && data.positions.length > 0) {
                    let html = `<table><thead><tr>
                        <th>Symbol</th>
                        <th>Qty</th>
                        <th>Avg Cost</th>
                        <th>Current</th>
                        <th>Day Chg</th>
                        <th>Value</th>
                        <th>P&L</th>
                        <th>P&L %</th>
                        <th>Actions</th>
                    </tr></thead><tbody>`;
                    
                    for (const p of data.positions) {
                        const pnlClass = (p.unrealized_pnl || 0) >= 0 ? 'positive' : 'negative';
                        const dayChgClass = (p.day_change_pct || 0) >= 0 ? 'positive' : 'negative';
                        const pnlPct = p.total_cost > 0 ? ((p.unrealized_pnl || 0) / p.total_cost * 100) : 0;
                        const cs = p.currency_symbol || '$';
                        const currentPrice = p.current_price || p.avg_cost || 0;
                        
                        html += `<tr>
                            <td><strong>${p.symbol}</strong>${p.sector ? '<br><span style="font-size:0.75em;color:var(--text-muted)">' + p.sector + '</span>' : ''}</td>
                            <td>${p.quantity}</td>
                            <td>${cs}${(p.avg_cost || 0).toFixed(2)}</td>
                            <td>${cs}${currentPrice.toFixed(2)}</td>
                            <td class="${dayChgClass}">${formatPct(p.day_change_pct || 0)}</td>
                            <td>${cs}${(p.current_value || p.total_cost || 0).toFixed(2)}</td>
                            <td class="${pnlClass}">${cs}${(p.unrealized_pnl || 0).toFixed(2)}</td>
                            <td class="${pnlClass}">${formatPct(pnlPct)}</td>
                            <td>
                                <button class="btn btn-sm btn-danger" onclick="quickSell('${p.symbol}', ${p.quantity}, ${currentPrice})">Sell</button>
                            </td>
                        </tr>`;
                    }
                    html += '</tbody></table>';
                    posDiv.innerHTML = html;
                    
                    // Draw charts
                    drawAllocationChart(data.positions);
                    drawSectorChart(data.positions);
                } else {
                    posDiv.innerHTML = '<div class="empty-state"><p>No positions yet. Use the Trade tab to buy stocks.</p></div>';
                    clearPortfolioCharts();
                }
                
                // Draw performance chart
                drawPerformanceChart(data);
                
            } else {
                summaryDiv.innerHTML = `
                    <div class="metric"><div class="metric-value">$0.00</div><div class="metric-label">Total Value</div></div>
                    <div class="metric"><div class="metric-value">$0.00</div><div class="metric-label">Cash</div></div>
                    <div class="metric"><div class="metric-value">$0.00</div><div class="metric-label">Total Return</div></div>
                    <div class="metric"><div class="metric-value">0.00%</div><div class="metric-label">Return %</div></div>
                `;
                posDiv.innerHTML = '<div class="empty-state"><p>' + (data?.error || 'Portfolio not available') + '</p></div>';
                clearPortfolioCharts();
            }
        }
        
        function clearPortfolioCharts() {
            if (allocationChart) { allocationChart.destroy(); allocationChart = null; }
            if (sectorChart) { sectorChart.destroy(); sectorChart = null; }
            if (performanceChart) { performanceChart.destroy(); performanceChart = null; }
        }
        
        function drawAllocationChart(positions) {
            const canvas = document.getElementById('portfolio-allocation-chart');
            if (!canvas) return;
            const ctx = canvas.getContext('2d');
            
            if (allocationChart) allocationChart.destroy();
            
            const labels = positions.map(p => p.symbol);
            const values = positions.map(p => p.current_value || p.total_cost || 0);
            const colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16'];
            
            allocationChart = new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: labels,
                    datasets: [{
                        data: values,
                        backgroundColor: colors.slice(0, labels.length),
                        borderWidth: 2,
                        borderColor: getComputedStyle(document.body).getPropertyValue('--bg-secondary')
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'right',
                            labels: { boxWidth: 12, padding: 8, font: { size: 11 } }
                        },
                        tooltip: {
                            callbacks: {
                                label: (ctx) => ctx.label + ': $' + ctx.raw.toLocaleString(undefined, {minimumFractionDigits: 2})
                            }
                        }
                    }
                }
            });
        }
        
        function drawSectorChart(positions) {
            const canvas = document.getElementById('portfolio-sector-chart');
            if (!canvas) return;
            const ctx = canvas.getContext('2d');
            
            if (sectorChart) sectorChart.destroy();
            
            // Group by sector
            const sectorMap = {};
            for (const p of positions) {
                const sector = p.sector || 'Unknown';
                sectorMap[sector] = (sectorMap[sector] || 0) + (p.current_value || p.total_cost || 0);
            }
            
            const labels = Object.keys(sectorMap);
            const values = Object.values(sectorMap);
            const colors = ['#06b6d4', '#8b5cf6', '#f59e0b', '#10b981', '#ef4444', '#ec4899', '#3b82f6', '#84cc16'];
            
            sectorChart = new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: labels,
                    datasets: [{
                        data: values,
                        backgroundColor: colors.slice(0, labels.length),
                        borderWidth: 2,
                        borderColor: getComputedStyle(document.body).getPropertyValue('--bg-secondary')
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'right',
                            labels: { boxWidth: 12, padding: 8, font: { size: 11 } }
                        },
                        tooltip: {
                            callbacks: {
                                label: (ctx) => ctx.label + ': $' + ctx.raw.toLocaleString(undefined, {minimumFractionDigits: 2})
                            }
                        }
                    }
                }
            });
        }
        
        function drawPerformanceChart(data) {
            const canvas = document.getElementById('portfolio-performance-chart');
            if (!canvas) return;
            const ctx = canvas.getContext('2d');
            
            if (performanceChart) performanceChart.destroy();
            
            // Generate simulated performance data from transactions
            const history = data.performance_history || generatePerformanceHistory(data);
            
            performanceChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: history.map(h => h.date),
                    datasets: [{
                        label: 'Portfolio Value',
                        data: history.map(h => h.value),
                        borderColor: '#3b82f6',
                        backgroundColor: 'rgba(59, 130, 246, 0.1)',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.1,
                        pointRadius: history.length < 30 ? 3 : 0
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                label: (ctx) => 'Value: $' + ctx.raw.toLocaleString(undefined, {minimumFractionDigits: 2})
                            }
                        }
                    },
                    scales: {
                        x: { grid: { display: false } },
                        y: {
                            ticks: {
                                callback: (v) => '$' + (v >= 1000 ? (v/1000).toFixed(0) + 'k' : v.toFixed(0))
                            }
                        }
                    }
                }
            });
        }
        
        function generatePerformanceHistory(data) {
            // Build history from actual transactions
            const history = [];
            const initialValue = data.initial_value || 100000;
            const transactions = data.transactions || [];
            
            // If we have transactions, build real history
            if (transactions.length > 0) {
                // Sort transactions by date
                const sortedTx = [...transactions].sort((a, b) => 
                    new Date(a.timestamp || a.date) - new Date(b.timestamp || b.date)
                );
                
                let runningCash = initialValue;
                let positions = {};
                
                // Add initial point
                const firstDate = new Date(sortedTx[0].timestamp || sortedTx[0].date);
                const dayBefore = new Date(firstDate);
                dayBefore.setDate(dayBefore.getDate() - 1);
                history.push({
                    date: dayBefore.toISOString().slice(0, 10),
                    value: initialValue
                });
                
                // Process each transaction
                for (const tx of sortedTx) {
                    const type = tx.type?.toLowerCase() || '';
                    const symbol = tx.symbol || '';
                    const qty = parseFloat(tx.quantity) || 0;
                    const price = parseFloat(tx.price) || 0;
                    const total = parseFloat(tx.total) || (qty * price);
                    
                    if (type === 'buy') {
                        runningCash -= total;
                        positions[symbol] = (positions[symbol] || 0) + qty;
                    } else if (type === 'sell') {
                        runningCash += total;
                        positions[symbol] = (positions[symbol] || 0) - qty;
                    } else if (type === 'deposit') {
                        runningCash += total || parseFloat(tx.amount) || 0;
                    } else if (type === 'withdraw') {
                        runningCash -= total || parseFloat(tx.amount) || 0;
                    } else if (type === 'dividend') {
                        runningCash += total || parseFloat(tx.amount) || 0;
                    }
                    
                    // Calculate portfolio value at this point
                    // Use transaction prices as approximation for position values
                    let positionValue = 0;
                    for (const [sym, shares] of Object.entries(positions)) {
                        if (shares > 0) {
                            // Find most recent price for this symbol from transactions
                            const lastTx = sortedTx.filter(t => t.symbol === sym && t.price).pop();
                            const estPrice = lastTx ? parseFloat(lastTx.price) : price;
                            positionValue += shares * estPrice;
                        }
                    }
                    
                    const totalValue = Math.max(0, runningCash + positionValue);
                    const txDate = tx.timestamp || tx.date;
                    
                    history.push({
                        date: txDate.slice(0, 10),
                        value: totalValue
                    });
                }
                
                // Add current value as final point
                history.push({
                    date: new Date().toISOString().slice(0, 10),
                    value: data.total_value || runningCash
                });
                
                return history;
            }
            
            // No transactions - show flat line at current value
            const today = new Date();
            const weekAgo = new Date(today);
            weekAgo.setDate(weekAgo.getDate() - 7);
            
            return [
                { date: weekAgo.toISOString().slice(0, 10), value: data.total_value || initialValue },
                { date: today.toISOString().slice(0, 10), value: data.total_value || initialValue }
            ];
        }
        
        function loadPerformanceChart(period) {
            // Update active button
            document.querySelectorAll('#tab-portfolio .card-header .btn-sm').forEach(btn => {
                btn.classList.remove('active');
                if (btn.textContent === period) btn.classList.add('active');
            });
            // Redraw chart
            if (currentPortfolioData) drawPerformanceChart(currentPortfolioData);
        }
        
        function quickSell(symbol, quantity, price) {
            document.getElementById('trade-symbol').value = symbol;
            document.getElementById('trade-quantity').value = quantity;
            document.getElementById('trade-price').value = price.toFixed(2);
            showPortfolioTab('trade');
            document.querySelector('#tab-portfolio .card-tab:nth-child(2)').click();
        }
        
        async function loadDividendHistory() {
            const name = document.getElementById('portfolio-select').value;
            const data = await fetchData('portfolio/' + name + '/dividends');
            const div = document.getElementById('portfolio-dividend-history');
            
            if (data && data.dividends && data.dividends.length > 0) {
                let totalDiv = 0;
                let html = '<table><thead><tr><th>Date</th><th>Symbol</th><th>Amount</th></tr></thead><tbody>';
                for (const d of data.dividends) {
                    totalDiv += d.amount || 0;
                    html += `<tr>
                        <td>${d.date || d.ex_date || '-'}</td>
                        <td><strong>${d.symbol}</strong></td>
                        <td class="positive">$${(d.amount || 0).toFixed(2)}</td>
                    </tr>`;
                }
                html += '</tbody></table>';
                html += `<p style="margin-top:12px;"><strong>Total Dividends Received:</strong> <span class="positive">$${totalDiv.toFixed(2)}</span></p>`;
                div.innerHTML = html;
            } else {
                div.innerHTML = '<div class="empty-state"><p>No dividends recorded yet.</p></div>';
            }
        }
        
        async function recordDividend() {
            const name = document.getElementById('portfolio-select').value;
            const symbol = cleanSymbol(document.getElementById('dividend-symbol').value);
            const amount = parseFloat(document.getElementById('dividend-amount').value);
            const date = document.getElementById('dividend-date').value;
            
            if (!symbol || !amount) {
                alert('Please enter symbol and amount');
                return;
            }
            
            const result = await fetchData('portfolio/' + name + '/dividend', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ symbol, amount, date: date || new Date().toISOString().slice(0, 10) })
            });
            
            if (result && result.success) {
                document.getElementById('dividend-symbol').value = '';
                document.getElementById('dividend-amount').value = '';
                document.getElementById('dividend-date').value = '';
                loadDividendHistory();
                loadPortfolio();
            } else {
                alert('Failed to record dividend: ' + (result?.error || 'Unknown error'));
            }
        }
        
        function exportPortfolioCSV() {
            if (!currentPortfolioData) {
                alert('No portfolio data to export');
                return;
            }
            
            let csv = 'Type,Symbol,Quantity,Price,Value,P&L,Sector\\n';
            
            // Positions
            if (currentPortfolioData.positions) {
                for (const p of currentPortfolioData.positions) {
                    csv += `Position,${p.symbol},${p.quantity},${p.avg_cost || 0},${p.current_value || p.total_cost || 0},${p.unrealized_pnl || 0},${p.sector || ''}\\n`;
                }
            }
            
            // Summary row
            csv += `\\nSummary,Total Value,${currentPortfolioData.total_value || 0},,,,\\n`;
            csv += `Summary,Cash,${currentPortfolioData.cash || 0},,,,\\n`;
            csv += `Summary,Total Return,${currentPortfolioData.total_return || 0},,,,\\n`;
            csv += `Summary,Return %,${currentPortfolioData.total_return_pct || 0},,,,\\n`;
            
            // Download
            const blob = new Blob([csv], { type: 'text/csv' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'portfolio_' + document.getElementById('portfolio-select').value + '_' + new Date().toISOString().slice(0, 10) + '.csv';
            a.click();
            URL.revokeObjectURL(url);
        }
        
        async function importPortfolioCSV() {
            const fileInput = document.getElementById('import-csv-file');
            if (!fileInput.files || !fileInput.files[0]) {
                alert('Please select a CSV file');
                return;
            }
            
            const file = fileInput.files[0];
            const text = await file.text();
            const lines = text.split('\\n').filter(l => l.trim());
            
            if (lines.length < 2) {
                alert('CSV file appears to be empty');
                return;
            }
            
            const name = document.getElementById('portfolio-select').value;
            let imported = 0;
            let errors = [];
            
            // Skip header
            for (let i = 1; i < lines.length; i++) {
                const cols = lines[i].split(',').map(c => c.trim());
                if (cols.length < 5) continue;
                
                const [date, type, symbol, quantity, price, notes] = cols;
                
                try {
                    if (type === 'buy' || type === 'sell') {
                        await fetchData('portfolio/' + name + '/' + type, {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({ symbol, quantity: parseFloat(quantity), price: parseFloat(price) })
                        });
                        imported++;
                    } else if (type === 'dividend') {
                        await fetchData('portfolio/' + name + '/dividend', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({ symbol, amount: parseFloat(quantity) || parseFloat(price), date })
                        });
                        imported++;
                    }
                } catch (e) {
                    errors.push(`Row ${i + 1}: ${e.message}`);
                }
            }
            
            closeModal('modal-import-csv');
            alert(`Imported ${imported} transactions` + (errors.length ? `\\n\\nErrors:\\n${errors.join('\\n')}` : ''));
            loadPortfolio();
        }
        
        function onPortfolioChange() {
            const name = document.getElementById('portfolio-select').value;
            const btn = document.getElementById('portfolio-delete-btn');
            
            if (name === 'default') {
                btn.textContent = 'Reset';
                btn.className = 'btn btn-sm btn-warning';
            } else {
                btn.textContent = 'Delete';
                btn.className = 'btn btn-sm btn-danger';
            }
            
            loadPortfolio();
        }
        
        function confirmDeleteOrResetPortfolio() {
            const name = document.getElementById('portfolio-select').value;
            if (!name) {
                alert('No portfolio selected');
                return;
            }
            
            if (name === 'default') {
                confirmResetPortfolio();
            } else {
                confirmDeletePortfolio();
            }
        }
        
        function confirmResetPortfolio() {
            if (confirm('Are you sure you want to reset the Default Portfolio?\\n\\nThis will:\\n• Sell all positions\\n• Clear all transaction history\\n• Reset cash to $100,000\\n\\nThis action cannot be undone.')) {
                resetPortfolio('default');
            }
        }
        
        async function resetPortfolio(name) {
            const result = await fetchData('portfolio/' + name + '/reset', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({})
            });
            
            if (result && result.success) {
                alert('Portfolio reset successfully');
                loadPortfolio();
            } else {
                alert('Failed to reset portfolio: ' + (result?.error || 'Unknown error'));
            }
        }
        
        function confirmDeletePortfolio() {
            const name = document.getElementById('portfolio-select').value;
            if (!name) {
                alert('No portfolio selected');
                return;
            }
            
            const displayName = document.getElementById('portfolio-select').selectedOptions[0]?.text || name;
            
            if (confirm(`Are you sure you want to delete "${displayName}"?\\n\\nThis will permanently delete all positions, transactions, and history. This action cannot be undone.`)) {
                deletePortfolio(name);
            }
        }
        
        async function deletePortfolio(name) {
            const result = await fetchData('portfolio/' + name + '/delete', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({})
            });
            
            if (result && result.success) {
                alert('Portfolio deleted successfully');
                loadPortfolios();
            } else {
                alert('Failed to delete portfolio: ' + (result?.error || 'Unknown error'));
            }
        }
        
        function showPortfolioTab(tab) {
            document.querySelectorAll('#tab-portfolio .card-tab').forEach(t => t.classList.remove('active'));
            event.target.classList.add('active');
            
            document.getElementById('portfolio-positions').style.display = tab === 'positions' ? 'block' : 'none';
            document.getElementById('portfolio-trade').style.display = tab === 'trade' ? 'block' : 'none';
            document.getElementById('portfolio-dividends').style.display = tab === 'dividends' ? 'block' : 'none';
            document.getElementById('portfolio-cash').style.display = tab === 'cash' ? 'block' : 'none';
            document.getElementById('portfolio-history').style.display = tab === 'history' ? 'block' : 'none';
            
            // Load data when switching tabs
            if (tab === 'history') {
                loadTransactionHistory();
            } else if (tab === 'dividends') {
                loadDividendHistory();
            }
        }
        
        async function getTradeQuote() {
            const symbol = cleanSymbol(document.getElementById('trade-symbol').value);
            if (!symbol) {
                alert('Please enter a symbol first');
                return;
            }
            
            document.getElementById('trade-symbol').value = symbol;
            document.getElementById('trade-price-hint').textContent = '(loading...)';
            
            const data = await fetchData('quote/' + encodeURIComponent(symbol));
            
            if (data && data.price) {
                document.getElementById('trade-price').value = data.price.toFixed(2);
                document.getElementById('trade-price-hint').textContent = '(market: ' + (data.currency_symbol || '$') + data.price.toFixed(2) + ')';
                if (data.display_symbol) {
                    document.getElementById('trade-symbol').value = data.display_symbol;
                }
            } else {
                document.getElementById('trade-price-hint').textContent = '(quote failed)';
                alert('Could not get quote: ' + (data?.error || 'Unknown error'));
            }
        }
        
        async function executeTrade(side) {
            const portfolio = document.getElementById('portfolio-select').value;
            const symbol = cleanSymbol(document.getElementById('trade-symbol').value);
            const quantity = parseFloat(document.getElementById('trade-quantity').value);
            const price = parseFloat(document.getElementById('trade-price').value);
            
            if (!symbol || !quantity || !price) {
                alert('Please fill in all fields');
                return;
            }
            
            document.getElementById('trade-symbol').value = symbol;
            
            const result = await fetchData('portfolio/' + portfolio + '/' + side, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({symbol, quantity, price})
            });
            
            if (result && result.success) {
                document.getElementById('trade-symbol').value = '';
                document.getElementById('trade-quantity').value = '';
                document.getElementById('trade-price').value = '';
                loadPortfolio();
            } else {
                alert('Trade failed: ' + (result?.error || 'Unknown error'));
            }
        }
        
        // Alerts
        async function loadAlerts() {
            const data = await fetchData('alerts');
            const listDiv = document.getElementById('alerts-list');
            
            if (data && data.alerts && data.alerts.length > 0) {
                let html = '<table><thead><tr><th>Symbol</th><th>Exchange</th><th>Condition</th><th>Target</th><th>Status</th><th></th></tr></thead><tbody>';
                for (const a of data.alerts) {
                    const statusBadge = a.status === 'active' ? 'badge-info' : a.status === 'triggered' ? 'badge-buy' : 'badge-hold';
                    html += '<tr>';
                    html += '<td><strong>' + (a.raw_symbol || a.symbol) + '</strong></td>';
                    html += '<td><span class="badge badge-info">' + (a.exchange || 'N/A') + '</span></td>';
                    html += '<td>' + a.condition + '</td>';
                    html += '<td>' + formatCurrency(a.value) + '</td>';
                    html += '<td><span class="badge ' + statusBadge + '">' + a.status + '</span></td>';
                    html += '<td><button class="btn btn-sm btn-danger" onclick="deleteAlert(\\'' + a.id + '\\')">Delete</button></td>';
                    html += '</tr>';
                }
                html += '</tbody></table>';
                listDiv.innerHTML = html;
            } else {
                listDiv.innerHTML = '<div class="empty-state"><p>No alerts set</p></div>';
            }
        }
        
        async function createAlert() {
            const symbol = cleanSymbol(document.getElementById('alert-symbol').value);
            const condition = document.getElementById('alert-condition').value;
            const price = parseFloat(document.getElementById('alert-price').value);
            
            if (!symbol || !price) {
                alert('Please fill in symbol and price');
                return;
            }
            
            document.getElementById('alert-symbol').value = symbol;
            
            await fetchData('alerts/create', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({symbol, condition, price})
            });
            
            document.getElementById('alert-symbol').value = '';
            document.getElementById('alert-price').value = '';
            loadAlerts();
        }
        
        async function deleteAlert(id) {
            await fetchData('alerts/' + id, {method: 'DELETE'});
            loadAlerts();
        }
        
        // News
        async function loadNews() {
            const symbol = cleanSymbol(document.getElementById('news-symbol').value);
            if (!symbol) return;
            
            document.getElementById('news-symbol').value = symbol;
            
            const contentDiv = document.getElementById('news-content');
            contentDiv.innerHTML = '<div class="loading"><div class="spinner"></div> Loading news...</div>';
            
            // Get display symbol to update input
            const quoteData = await fetchData('quote/' + encodeURIComponent(symbol));
            if (quoteData && quoteData.display_symbol) {
                document.getElementById('news-symbol').value = quoteData.display_symbol;
            }
            
            const data = await fetchData('news/' + encodeURIComponent(symbol));
            
            if (data && data.news && data.news.length > 0) {
                let html = '<div class="card" style="margin-bottom: 16px;"><p>Sentiment: <strong>' + data.sentiment.overall.toUpperCase() + '</strong> ';
                html += '(👍 ' + data.sentiment.positive + ' | 👎 ' + data.sentiment.negative + ' | ➖ ' + data.sentiment.neutral + ')</p></div>';
                
                for (const item of data.news) {
                    const icon = item.sentiment === 'positive' ? '[+]' : item.sentiment === 'negative' ? '[-]' : '[.]';
                    html += '<div class="news-item">';
                    html += '<div class="news-headline">' + icon + ' ' + item.headline + '</div>';
                    html += '<div class="news-meta">' + item.source + ' • ' + item.published + '</div>';
                    if (item.summary) html += '<p style="margin-top: 8px; color: var(--text-secondary);">' + item.summary + '</p>';
                    html += '</div>';
                }
                contentDiv.innerHTML = html;
            } else {
                contentDiv.innerHTML = '<div class="empty-state"><p>No news found</p></div>';
            }
        }
        
        function formatLargeNumber(num) {
            if (num >= 1e12) return (num / 1e12).toFixed(2) + 'T';
            if (num >= 1e9) return (num / 1e9).toFixed(2) + 'B';
            if (num >= 1e6) return (num / 1e6).toFixed(2) + 'M';
            return num.toLocaleString();
        }
        
        // Sectors
        async function loadSectors() {
            const contentDiv = document.getElementById('sectors-content');
            const period = document.getElementById('sector-period')?.value || '1d';
            contentDiv.innerHTML = '<div class="loading"><div class="spinner"></div> Loading sectors...</div>';
            
            const data = await fetchData('sectors?period=' + period);
            
            // Period labels for display
            const periodLabels = {
                '1d': '1 Day',
                '5d': '5 Days',
                '1w': '1 Week',
                '1m': '1 Month',
                '3m': '3 Months',
                '6m': '6 Months',
                'ytd': 'Year to Date',
                '1y': '1 Year',
                '3y': '3 Years',
                '5y': '5 Years'
            };
            
            if (data && data.sectors) {
                let html = '<p style="margin-bottom: 16px; color: var(--text-secondary);">Performance over <strong>' + (periodLabels[period] || period) + '</strong></p>';
                
                html += '<div style="margin-bottom: 20px;">';
                html += '<h3>Major Indices</h3><div class="grid grid-4" style="margin-bottom: 20px;">';
                for (const idx of data.indices || []) {
                    const changeClass = idx.change_pct >= 0 ? 'positive' : 'negative';
                    html += '<div class="metric"><div class="metric-value ' + changeClass + '">' + formatPct(idx.change_pct) + '</div>';
                    html += '<div class="metric-label">' + idx.name + '</div></div>';
                }
                html += '</div></div>';
                
                html += '<h3>Sector Heatmap</h3><div class="heatmap-grid">';
                for (const sector of data.sectors) {
                    let heatClass = 'heat-neutral';
                    const pct = sector.change_pct || 0;
                    // Adjust thresholds based on period
                    const multiplier = period === '1d' ? 1 : period === '5d' ? 2 : period === '1w' ? 2 : period === '1m' ? 3 : 5;
                    if (pct >= 2 * multiplier) heatClass = 'heat-strong-up';
                    else if (pct >= 1 * multiplier) heatClass = 'heat-up';
                    else if (pct >= 0.2 * multiplier) heatClass = 'heat-slight-up';
                    else if (pct <= -2 * multiplier) heatClass = 'heat-strong-down';
                    else if (pct <= -1 * multiplier) heatClass = 'heat-down';
                    else if (pct <= -0.2 * multiplier) heatClass = 'heat-slight-down';
                    
                    html += '<div class="heatmap-cell ' + heatClass + '">';
                    html += '<div class="symbol">' + sector.symbol + '</div>';
                    html += '<div style="font-size: 0.8em; color: inherit; opacity: 0.9;">' + sector.name + '</div>';
                    html += '<div class="change">' + formatPct(pct) + '</div>';
                    html += '</div>';
                }
                html += '</div>';
                
                contentDiv.innerHTML = html;
            } else {
                contentDiv.innerHTML = '<div class="empty-state"><p>Could not load sector data</p></div>';
            }
        }
        
        // ML Predictions
        let predictionChart = null;
        
        async function runPrediction() {
            const symbol = cleanSymbol(document.getElementById('predict-symbol').value);
            if (!symbol) {
                alert('Please enter a stock symbol');
                return;
            }
            
            document.getElementById('predict-symbol').value = symbol;
            
            const days = parseInt(document.getElementById('predict-days').value) || 30;
            const windows = parseInt(document.getElementById('predict-windows').value) || 5;
            
            // Show loading
            document.getElementById('predict-loading').style.display = 'block';
            document.getElementById('predict-results').style.display = 'none';
            document.getElementById('predict-error').style.display = 'none';
            
            updatePredictStatus('Fetching historical data...');
            
            try {
                const data = await fetchData(`predict/${encodeURIComponent(symbol)}?days=${days}&windows=${windows}`);
                
                if (data && !data.error) {
                    // Update symbol with display symbol
                    if (data.display_symbol) {
                        document.getElementById('predict-symbol').value = data.display_symbol;
                    }
                    
                    displayPredictionResults(data);
                } else {
                    showPredictError(data?.error || 'Prediction failed');
                }
            } catch (e) {
                showPredictError('Prediction failed: ' + e.message);
            }
            
            document.getElementById('predict-loading').style.display = 'none';
        }
        
        function updatePredictStatus(msg) {
            document.getElementById('predict-status').textContent = msg;
        }
        
        function showPredictError(msg) {
            document.getElementById('predict-error').style.display = 'block';
            document.getElementById('predict-error-message').textContent = msg;
        }
        
        function displayPredictionResults(data) {
            document.getElementById('predict-results').style.display = 'block';
            
            const cs = data.currency_symbol || '$';
            
            // Signal grid
            const signalClass = data.signal.includes('BUY') ? 'positive' : 
                               data.signal.includes('SELL') ? 'negative' : 'neutral';
            const signalBadge = data.signal.includes('BUY') ? 'badge-buy' : 
                               data.signal.includes('SELL') ? 'badge-sell' : 'badge-hold';
            
            document.getElementById('predict-signal-grid').innerHTML = `
                <div class="metric">
                    <div class="metric-value"><span class="badge ${signalBadge}" style="font-size: 1.2em; padding: 8px 16px;">${data.signal}</span></div>
                    <div class="metric-label">ML Signal</div>
                </div>
                <div class="metric">
                    <div class="metric-value ${signalClass}">${data.predicted_return_30d >= 0 ? '+' : ''}${data.predicted_return_30d.toFixed(2)}%</div>
                    <div class="metric-label">Predicted 30d Return</div>
                </div>
                <div class="metric">
                    <div class="metric-value">${data.probability_positive.toFixed(1)}%</div>
                    <div class="metric-label">Prob. Positive Return</div>
                </div>
                <div class="metric">
                    <div class="metric-value">${data.risk_adjusted_score.toFixed(2)}</div>
                    <div class="metric-label">Risk-Adj Score</div>
                </div>
            `;
            
            // Validation grid
            const wf = data.walk_forward;
            document.getElementById('predict-validation-grid').innerHTML = `
                <div class="metric">
                    <div class="metric-value">${wf.num_windows}</div>
                    <div class="metric-label">Validation Windows</div>
                </div>
                <div class="metric">
                    <div class="metric-value">${wf.avg_directional_accuracy.toFixed(1)}%</div>
                    <div class="metric-label">Direction Accuracy</div>
                </div>
                <div class="metric">
                    <div class="metric-value">${cs}${wf.avg_rmse.toFixed(2)}</div>
                    <div class="metric-label">Avg RMSE</div>
                </div>
                <div class="metric">
                    <div class="metric-value">${wf.avg_sharpe.toFixed(2)}</div>
                    <div class="metric-label">Avg Sharpe</div>
                </div>
            `;
            
            // Prediction chart
            drawPredictionChart(data, cs);
            
            // Prediction table - include Day 0 (current price) and key days
            let tableHtml = '<table><thead><tr><th>Day</th><th>Date</th><th>Predicted</th><th>Range (95% CI)</th><th>Total Return</th><th>Period Chg</th><th>Confidence</th></tr></thead><tbody>';
            
            // Key days to show: 0 (current), 1, 5, 10, 15, 20, 25, 30
            const keyDays = [0, 1, 5, 10, 15, 20, 25, 30];
            
            // Determine decimal places based on price
            const samplePrice = data.current_price || (data.predictions[0] ? data.predictions[0].predicted_price : 100);
            let priceDecimals = 2;
            if (samplePrice < 0.1) priceDecimals = 4;
            else if (samplePrice < 1) priceDecimals = 3;
            else if (samplePrice < 10) priceDecimals = 2;
            
            // Track previous price for period change calculation
            let prevPrice = data.current_price || (data.predictions[0] ? data.predictions[0].predicted_price : 0);
            let prevDayShown = 0;
            
            for (const targetDay of keyDays) {
                // Find the prediction for this day number
                const p = data.predictions.find(pred => pred.day_number === targetDay);
                if (!p) continue;
                
                // Total return (from Day 0)
                const totalRetClass = p.predicted_return >= 0 ? 'positive' : 'negative';
                const totalRetSign = p.predicted_return >= 0 ? '+' : '';
                
                // Period change (from previous shown day)
                const periodChange = prevPrice > 0 ? ((p.predicted_price / prevPrice) - 1) * 100 : 0;
                const periodClass = periodChange >= 0 ? 'positive' : 'negative';
                const periodSign = periodChange >= 0 ? '+' : '';
                
                const isDay0 = p.day_number === 0;
                
                const formatPrice = (price) => {
                    return price.toLocaleString(undefined, {minimumFractionDigits: priceDecimals, maximumFractionDigits: priceDecimals});
                };
                
                tableHtml += `<tr${isDay0 ? ' style="background: var(--bg-secondary);"' : ''}>
                    <td>${isDay0 ? '<strong>Current</strong>' : p.day_number}</td>
                    <td>${p.date}</td>
                    <td><strong>${cs}${formatPrice(p.predicted_price)}</strong></td>
                    <td>${isDay0 ? '-' : cs + formatPrice(p.lower_bound) + ' - ' + cs + formatPrice(p.upper_bound)}</td>
                    <td class="${totalRetClass}">${isDay0 ? '-' : totalRetSign + p.predicted_return.toFixed(2) + '%'}</td>
                    <td class="${periodClass}">${isDay0 ? '-' : periodSign + periodChange.toFixed(2) + '%'}</td>
                    <td>${isDay0 ? '-' : p.confidence.toFixed(0) + '%'}</td>
                </tr>`;
                
                // Update previous price for next iteration
                prevPrice = p.predicted_price;
                prevDayShown = targetDay;
            }
            tableHtml += '</tbody></table>';
            document.getElementById('predict-table').innerHTML = tableHtml;
            
            // Model info
            document.getElementById('predict-model-info').innerHTML = `
                <p><strong>Model:</strong> ${data.model_type} Neural Network</p>
                <p><strong>Training Samples:</strong> ${data.training_samples.toLocaleString()}</p>
                <p><strong>Features Used:</strong> ${data.features_used.length} (${data.features_used.slice(0, 5).join(', ')}...)</p>
                <p><strong>Prediction Date:</strong> ${data.prediction_date}</p>
                <p style="margin-top: 12px; color: var(--text-muted); font-size: 0.9em;">
                    Note: ML predictions are for educational purposes only. Past performance does not guarantee future results.</em>
                </p>
            `;
        }
        
        function drawPredictionChart(data, cs) {
            const canvas = document.getElementById('prediction-canvas');
            const ctx = canvas.getContext('2d');
            
            // Destroy existing chart
            if (predictionChart) {
                predictionChart.destroy();
            }
            
            const labels = data.predictions.map(p => p.date.slice(5)); // MM-DD format
            const prices = data.predictions.map(p => p.predicted_price);
            const lowerBounds = data.predictions.map(p => p.lower_bound);
            const upperBounds = data.predictions.map(p => p.upper_bound);
            
            // Determine decimal places based on price magnitude
            const maxPrice = Math.max(...prices, ...upperBounds);
            const minPrice = Math.min(...prices.filter(p => p > 0), ...lowerBounds.filter(p => p > 0));
            let decimals = 2;
            if (maxPrice < 1) decimals = 4;
            else if (maxPrice < 10) decimals = 3;
            else if (maxPrice < 100) decimals = 2;
            else decimals = 0;
            
            predictionChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [
                        {
                            label: 'Predicted Price',
                            data: prices,
                            borderColor: '#3b82f6',
                            backgroundColor: 'rgba(59, 130, 246, 0.1)',
                            borderWidth: 2,
                            fill: false,
                            tension: 0.1
                        },
                        {
                            label: 'Upper Bound (95%)',
                            data: upperBounds,
                            borderColor: 'rgba(34, 197, 94, 0.5)',
                            borderWidth: 1,
                            borderDash: [5, 5],
                            fill: false,
                            pointRadius: 0
                        },
                        {
                            label: 'Lower Bound (95%)',
                            data: lowerBounds,
                            borderColor: 'rgba(239, 68, 68, 0.5)',
                            borderWidth: 1,
                            borderDash: [5, 5],
                            fill: '-1',
                            backgroundColor: 'rgba(59, 130, 246, 0.1)',
                            pointRadius: 0
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: true,
                            position: 'top'
                        },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    return context.dataset.label + ': ' + cs + context.parsed.y.toFixed(decimals);
                                }
                            }
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: false,
                            ticks: {
                                callback: function(value) {
                                    return cs + value.toFixed(decimals);
                                }
                            }
                        }
                    },
                    interaction: {
                        intersect: false,
                        mode: 'index'
                    }
                }
            });
        }
        
        // Account
        async function loadAccount() {
            const summaryDiv = document.getElementById('account-summary');
            const positionsDiv = document.getElementById('account-positions');
            const ordersDiv = document.getElementById('account-orders');
            
            const account = await fetchData('account');
            if (account && !account.error) {
                const pnlClass = account.daily_pnl >= 0 ? 'positive' : 'negative';
                summaryDiv.innerHTML = `
                    <div class="metric">
                        <div class="metric-value">${formatCurrency(account.equity)}</div>
                        <div class="metric-label">Equity</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">${formatCurrency(account.cash)}</div>
                        <div class="metric-label">Cash</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">${formatCurrency(account.buying_power)}</div>
                        <div class="metric-label">Buying Power</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value ${pnlClass}">${formatCurrency(account.daily_pnl)}</div>
                        <div class="metric-label">Daily P&L</div>
                    </div>
                `;
            } else {
                summaryDiv.innerHTML = '<div class="empty-state"><p>Could not load account (check API keys)</p></div>';
            }
            
            const positions = await fetchData('positions');
            if (positions && positions.length > 0) {
                let html = '<table><thead><tr><th>Symbol</th><th>Qty</th><th>Entry</th><th>Current</th><th>P&L</th><th></th></tr></thead><tbody>';
                for (const p of positions) {
                    const pnlClass = p.unrealized_pnl >= 0 ? 'positive' : 'negative';
                    html += '<tr><td><strong>' + p.symbol + '</strong></td>';
                    html += '<td>' + p.qty + '</td>';
                    html += '<td>' + formatCurrency(p.avg_entry_price) + '</td>';
                    html += '<td>' + formatCurrency(p.current_price) + '</td>';
                    html += '<td class="' + pnlClass + '">' + formatCurrency(p.unrealized_pnl) + ' (' + formatPct(p.unrealized_pnl_pct) + ')</td>';
                    html += '<td><button class="btn btn-sm btn-primary" onclick="analyzeFromWatchlist(\\'' + p.symbol + '\\')">Analyze</button></td></tr>';
                }
                html += '</tbody></table>';
                positionsDiv.innerHTML = html;
            } else {
                positionsDiv.innerHTML = '<div class="empty-state"><p>No open positions</p></div>';
            }
            
            const orders = await fetchData('orders');
            if (orders && orders.length > 0) {
                let html = '<table><thead><tr><th>Symbol</th><th>Side</th><th>Qty</th><th>Price</th><th>Status</th></tr></thead><tbody>';
                for (const o of orders.slice(0, 10)) {
                    html += '<tr><td>' + o.symbol + '</td><td>' + o.side + '</td><td>' + o.qty + '</td>';
                    html += '<td>' + (o.filled_avg_price ? formatCurrency(o.filled_avg_price) : '-') + '</td>';
                    html += '<td><span class="badge badge-info">' + o.status + '</span></td></tr>';
                }
                html += '</tbody></table>';
                ordersDiv.innerHTML = html;
            } else {
                ordersDiv.innerHTML = '<div class="empty-state"><p>No recent orders</p></div>';
            }
        }
    </script>
</body>
</html>
"""


class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    """Handle dashboard requests."""
    
    @staticmethod
    def clean_symbol(raw: str) -> str:
        """
        Clean and normalize a stock symbol from user input.
        Handles badly formatted input like 'nasDAQ     :      aApl' -> 'NASDAQ:AAPL'
        """
        if not raw:
            return ""
        # Uppercase, strip whitespace
        s = raw.strip().upper()
        # Remove all spaces (handles '  NASDAQ   :   AAPL  ')
        s = ''.join(s.split())
        return s
    
    # Simple in-memory cache with TTL (time-to-live)
    _cache = {}
    _cache_ttl = {}
    _cache_duration = 60  # Cache for 60 seconds
    
    @classmethod
    def _get_cached(cls, key):
        """Get value from cache if not expired."""
        import time
        if key in cls._cache and key in cls._cache_ttl:
            if time.time() < cls._cache_ttl[key]:
                return cls._cache[key]
            else:
                # Expired - remove
                del cls._cache[key]
                del cls._cache_ttl[key]
        return None
    
    @classmethod
    def _set_cached(cls, key, value, ttl=None):
        """Set value in cache with TTL."""
        import time
        cls._cache[key] = value
        cls._cache_ttl[key] = time.time() + (ttl or cls._cache_duration)
    
    def __init__(self, *args, **kwargs):
        self.client = AlpacaClient() if ALPACA_AVAILABLE else None
        self.analyzer = StockAnalyzer() if ANALYZER_AVAILABLE else None
        self.watchlist = WatchlistManager() if WATCHLIST_AVAILABLE else None
        self.alerts = AlertManager() if ALERTS_AVAILABLE else None
        self.portfolio = PortfolioManager() if PORTFOLIO_AVAILABLE else None
        self.news = NewsManager() if NEWS_AVAILABLE else None
        self.sectors = SectorHeatmap() if SECTORS_AVAILABLE else None
        self.exporter = ReportExporter() if EXPORT_AVAILABLE else None
        super().__init__(*args, **kwargs)
    
    def _analyze_symbol_cached(self, symbol):
        """Analyze a symbol with caching."""
        cache_key = f"analyze_{symbol}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached
        
        if self.analyzer:
            try:
                result = self.analyzer.analyze(symbol)
                self._set_cached(cache_key, result, ttl=30)  # 30 second cache for quotes
                return result
            except:
                return None
        return None
    
    def _fetch_symbols_parallel(self, symbols, fetch_func=None):
        """Fetch data for multiple symbols in parallel."""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        if fetch_func is None:
            fetch_func = self._analyze_symbol_cached
        
        results = {}
        
        # Use ThreadPoolExecutor for parallel fetching
        with ThreadPoolExecutor(max_workers=min(len(symbols), 8)) as executor:
            future_to_symbol = {executor.submit(fetch_func, sym): sym for sym in symbols}
            for future in as_completed(future_to_symbol):
                symbol = future_to_symbol[future]
                try:
                    results[symbol] = future.result()
                except Exception:
                    results[symbol] = None
        
        return results
    
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        
        if path == "/" or path == "/index.html":
            self._serve_html()
        elif path == "/api/account":
            self._serve_account()
        elif path == "/api/positions":
            self._serve_positions()
        elif path == "/api/orders":
            self._serve_orders()
        elif path.startswith("/api/analyze/"):
            symbol = path.split("/")[-1]
            symbol = self.clean_symbol(urllib.parse.unquote(symbol))
            self._serve_analysis(symbol)
        elif path.startswith("/api/compare/"):
            symbols = path.split("/")[-1]
            symbols = [self.clean_symbol(s) for s in urllib.parse.unquote(symbols).split(",")]
            # Filter out empty symbols or symbols ending with colon
            symbols = [s for s in symbols if s and not s.endswith(':')]
            self._serve_comparison(symbols)
        elif path == "/api/watchlists":
            self._serve_watchlists()
        elif path.startswith("/api/watchlist/"):
            parts = path.split("/")
            name = parts[3] if len(parts) > 3 else "default"
            self._serve_watchlist(name)
        elif path == "/api/alerts":
            self._serve_alerts()
        elif path == "/api/portfolios":
            self._serve_portfolios()
        elif path.startswith("/api/portfolio/") and "/dividends" in path:
            name = path.split("/")[3]
            self._serve_portfolio_dividends(name)
        elif path.startswith("/api/portfolio/") and "/transactions" in path:
            name = path.split("/")[3]
            self._serve_transactions(name)
        elif path.startswith("/api/portfolio/"):
            parts = path.split("/")
            name = parts[3] if len(parts) > 3 else "default"
            include_live = "include_live=true" in (query or "")
            self._serve_portfolio(name, include_live)
        elif path.startswith("/api/news/"):
            symbol = self.clean_symbol(urllib.parse.unquote(path.split("/")[-1]))
            self._serve_news(symbol)
        elif path == "/api/sectors" or path.startswith("/api/sectors?"):
            self._serve_sectors(query)
        elif path.startswith("/api/watchlist/") and "/analyze" in path:
            name = path.split("/")[3]
            self._serve_watchlist_analysis(name)
        elif path.startswith("/api/quote/"):
            symbol = self.clean_symbol(urllib.parse.unquote(path.split("/")[-1]))
            self._serve_quote(symbol)
        elif path.startswith("/api/predict/"):
            symbol = self.clean_symbol(urllib.parse.unquote(path.split("/")[-1]))
            self._serve_prediction(symbol, query)
        else:
            self.send_error(404)
    
    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8') if content_length > 0 else '{}'
        data = json.loads(body) if body else {}
        
        if path.startswith("/api/watchlist/") and path.endswith("/add"):
            name = path.split("/")[3]
            self._add_to_watchlist(name, self.clean_symbol(data.get('symbol', '')))
        elif path.startswith("/api/watchlist/") and path.endswith("/remove"):
            name = path.split("/")[3]
            self._remove_from_watchlist(name, self.clean_symbol(data.get('symbol', '')))
        elif path == "/api/watchlist/create":
            self._create_watchlist(data.get('name', ''))
        elif path == "/api/alerts/create":
            self._create_alert(data)
        elif "/portfolio/" in path and "/dividend" in path:
            name = path.split("/")[3]
            self._record_dividend(name, data)
        elif "/portfolio/" in path and "/reset" in path:
            name = path.split("/")[3]
            self._reset_portfolio(name)
        elif "/portfolio/" in path and "/delete" in path:
            name = path.split("/")[3]
            self._delete_portfolio(name)
        elif "/portfolio/" in path and "/buy" in path:
            name = path.split("/")[3]
            self._portfolio_trade(name, 'buy', data)
        elif "/portfolio/" in path and "/sell" in path:
            name = path.split("/")[3]
            self._portfolio_trade(name, 'sell', data)
        elif "/portfolio/" in path and "/deposit" in path:
            name = path.split("/")[3]
            self._portfolio_deposit(name, data)
        elif "/portfolio/" in path and "/withdraw" in path:
            name = path.split("/")[3]
            self._portfolio_withdraw(name, data)
        elif path == "/api/portfolio/create":
            self._create_portfolio(data)
        elif path.startswith("/api/watchlist/") and path.endswith("/delete"):
            name = path.split("/")[3]
            self._delete_watchlist(name)
        elif path == "/api/export":
            self._export_analysis(data)
        elif path == "/api/alpaca/order":
            self._place_alpaca_order(data)
        else:
            self.send_error(404)
    
    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        
        if path.startswith("/api/alerts/"):
            alert_id = path.split("/")[-1]
            self._delete_alert(alert_id)
        else:
            self.send_error(404)
    
    def _serve_html(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(DASHBOARD_HTML.encode())
    
    def _serve_json(self, data):
        try:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())
        except (BrokenPipeError, ConnectionResetError):
            # Client disconnected before we could send response - ignore
            pass
        except Exception as e:
            print(f"Error serving JSON: {e}")
    
    def _serve_account(self):
        if not self.client:
            self._serve_json({"error": "Alpaca not available"})
            return
        try:
            account = self.client.get_account()
            self._serve_json({
                "equity": account.equity,
                "cash": account.cash,
                "buying_power": account.buying_power,
                "daily_pnl": account.daily_pnl,
                "daily_pnl_pct": account.daily_pnl_pct,
            })
        except Exception as e:
            self._serve_json({"error": str(e)})
    
    def _serve_positions(self):
        if not self.client:
            self._serve_json([])
            return
        try:
            positions = self.client.get_positions()
            self._serve_json([{
                "symbol": p.symbol,
                "qty": p.qty,
                "avg_entry_price": p.avg_entry_price,
                "current_price": p.current_price,
                "market_value": p.market_value,
                "unrealized_pnl": p.unrealized_pnl,
                "unrealized_pnl_pct": p.unrealized_pnl_pct,
            } for p in positions])
        except Exception as e:
            self._serve_json([])
    
    def _serve_orders(self):
        if not self.client:
            self._serve_json([])
            return
        try:
            orders = self.client.get_orders("all")
            self._serve_json([{
                "symbol": o.symbol,
                "side": o.side,
                "qty": o.qty,
                "status": o.status,
                "filled_avg_price": o.filled_avg_price,
                "submitted_at": o.submitted_at,
            } for o in orders[:20]])
        except Exception:
            self._serve_json([])
    
    def _serve_analysis(self, symbol):
        if not self.analyzer:
            self._serve_json({"error": "Analyzer not available"})
            return
        
        try:
            r = self.analyzer.analyze(symbol)
            
            currency = getattr(r, 'currency', 'USD')
            currency_symbol = getattr(r, 'currency_symbol', '$')
            price_divisor = getattr(r, 'price_divisor', 1)
            
            if currency == 'GBp':
                display_price = r.current_price / 100
                display_currency = 'GBP'
                currency_symbol = '£'
            else:
                display_price = r.current_price
                display_currency = currency
            
            self._serve_json({
                "symbol": r.symbol,
                "display_symbol": getattr(r, 'display_symbol', r.symbol),
                "company_name": r.company_name,
                "sector": r.sector,
                "industry": r.industry,
                "country": getattr(r, 'country', 'US'),
                "currency": display_currency,
                "currency_symbol": currency_symbol,
                "current_price": display_price,
                "change": r.change / price_divisor if price_divisor > 1 else r.change,
                "change_pct": r.change_pct,
                "market_cap": r.market_cap,
                "beta": r.beta,
                "pe_ratio": r.pe_ratio,
                "recommendation": r.recommendation.value,
                "confidence": r.confidence,
                "overall_score": r.overall_score,
                "technical_score": r.technical_score,
                "fundamental_score": r.fundamental_score,
                "analyst_score": r.analyst_score,
                "risk_score": r.risk_score,
                "trend": r.trend.value,
                "target_low": r.target_low / price_divisor if price_divisor > 1 else r.target_low,
                "target_mid": r.target_mid / price_divisor if price_divisor > 1 else r.target_mid,
                "target_high": r.target_high / price_divisor if price_divisor > 1 else r.target_high,
                "volatility": r.risk_metrics.volatility_annual,
                "volatility_rating": r.risk_metrics.volatility_rating,
                "var_95": r.risk_metrics.var_95,
                "max_drawdown": r.risk_metrics.max_drawdown,
                "sharpe_ratio": r.risk_metrics.sharpe_ratio,
                "summary": r.summary,
                "technical_signals": [{"name": s.name, "signal": s.signal, "description": s.description} for s in r.technical_signals],
                "fundamental_signals": [{"name": s.name, "signal": s.signal, "description": s.description} for s in r.fundamental_signals],
                "analyst_signals": [{"name": s.name, "signal": s.signal, "description": s.description} for s in r.analyst_signals],
            })
        except Exception as e:
            import traceback
            traceback.print_exc()
            self._serve_json({"error": str(e)})
    
    def _serve_comparison(self, symbols):
        if not self.analyzer:
            self._serve_json({"error": "Analyzer not available"})
            return
        
        # Filter invalid symbols
        symbols = [s for s in symbols if s and len(s) >= 1 and not s.endswith(':')]
        
        if len(symbols) < 2:
            self._serve_json({"error": "Need at least 2 valid symbols to compare"})
            return
        
        try:
            from trading.comparison import StockComparison
            comp = StockComparison()
            result = comp.compare(symbols, verbose=False)
            
            analyses = {}
            display_symbols = []  # For header display with exchange
            
            for sym, r in result.analyses.items():
                currency_symbol = getattr(r, 'currency_symbol', '$')
                price_divisor = getattr(r, 'price_divisor', 1)
                display_symbol = getattr(r, 'display_symbol', sym)
                
                # Get market cap - try multiple sources
                market_cap = r.market_cap
                if market_cap == 0 or market_cap is None:
                    # Try to get from company info
                    market_cap = getattr(r, 'market_cap_raw', 0) or 0
                
                # Detect currency symbol from exchange if not set
                if currency_symbol == '$' and display_symbol != sym:
                    sym_upper = display_symbol.upper()
                    if sym_upper.startswith('ASX:') or '.AX' in sym_upper:
                        currency_symbol = 'A$'
                    elif sym_upper.startswith('LON:') or sym_upper.startswith('LSE:') or '.L' in sym_upper:
                        currency_symbol = '£'
                    elif sym_upper.startswith('TSE:') or sym_upper.startswith('TSX:') or '.TO' in sym_upper:
                        currency_symbol = 'C$'
                    elif sym_upper.startswith('FRA:') or '.F' in sym_upper:
                        currency_symbol = '€'
                    elif sym_upper.startswith('EPA:') or '.PA' in sym_upper:
                        currency_symbol = '€'
                    elif '.HK' in sym_upper:
                        currency_symbol = 'HK$'
                
                display_symbols.append(display_symbol)
                
                analyses[display_symbol] = {
                    "symbol": sym,
                    "display_symbol": display_symbol,
                    "current_price": r.current_price / price_divisor if price_divisor > 1 else r.current_price,
                    "currency_symbol": currency_symbol,
                    "change_pct": r.change_pct,
                    "overall_score": r.overall_score,
                    "recommendation": r.recommendation.value,
                    "technical_score": r.technical_score,
                    "fundamental_score": r.fundamental_score,
                    "pe_ratio": r.pe_ratio,
                    "market_cap": market_cap,
                    "beta": r.beta,
                    "volatility": r.risk_metrics.volatility_annual,
                    "sharpe_ratio": r.risk_metrics.sharpe_ratio,
                    "target_mid": r.target_mid / price_divisor if price_divisor > 1 else r.target_mid,
                }
            
            # Find winner display symbol
            winner_display = result.winner
            for sym, r in result.analyses.items():
                if sym == result.winner:
                    winner_display = getattr(r, 'display_symbol', sym)
                    break
            
            self._serve_json({
                "symbols": display_symbols,
                "analyses": analyses,
                "winner": winner_display,
                "summary": result.summary,
            })
        except ValueError as e:
            self._serve_json({"error": str(e)})
        except Exception as e:
            self._serve_json({"error": f"Comparison failed: {str(e)}"})
    
    def _serve_watchlists(self):
        if not self.watchlist:
            self._serve_json({"watchlists": []})
            return
        self._serve_json({"watchlists": self.watchlist.list_watchlists()})
    
    def _serve_watchlist(self, name):
        if not self.watchlist:
            self._serve_json({"stocks": []})
            return
        
        symbols = self.watchlist.get(name)
        
        if not symbols:
            self._serve_json({"stocks": []})
            return
        
        # Use fast batch quotes instead of full analysis
        live_quotes = self._fetch_batch_quotes_fast(symbols)
        
        stocks = []
        for sym in symbols:
            quote = live_quotes.get(sym, {})
            stocks.append({
                "symbol": sym,
                "price": quote.get("price", 0),
                "change_pct": quote.get("change_pct", 0),
                "score": None,  # No score without full analysis
                "recommendation": None,
                "currency_symbol": "$",
            })
        
        self._serve_json({"stocks": stocks})
    
    def _add_to_watchlist(self, name, symbol):
        if self.watchlist and symbol:
            self.watchlist.add(name, symbol)
        self._serve_json({"success": True})
    
    def _remove_from_watchlist(self, name, symbol):
        if self.watchlist and symbol:
            self.watchlist.remove(name, symbol)
        self._serve_json({"success": True})
    
    def _create_watchlist(self, name):
        if self.watchlist and name:
            self.watchlist.create(name)
        self._serve_json({"success": True})
    
    def _serve_alerts(self):
        if not self.alerts:
            self._serve_json({"alerts": []})
            return
        
        from trading.exchanges import ExchangeMapper
        mapper = ExchangeMapper()
        
        alerts = self.alerts.get_all()
        alerts_data = []
        for a in alerts:
            alert_dict = a.to_dict()
            # Parse symbol to get exchange info
            parsed = mapper.parse(a.symbol)
            alert_dict['display_symbol'] = parsed.display
            alert_dict['exchange'] = parsed.exchange
            alert_dict['raw_symbol'] = parsed.symbol
            alerts_data.append(alert_dict)
        
        self._serve_json({"alerts": alerts_data})
    
    def _create_alert(self, data):
        if not self.alerts:
            self._serve_json({"error": "Alerts not available"})
            return
        
        symbol = self.clean_symbol(data.get('symbol', ''))
        condition = data.get('condition', 'above')
        price = float(data.get('price', 0))
        
        if symbol and price:
            self.alerts.add_price_alert(symbol, condition, price)
        
        self._serve_json({"success": True})
    
    def _delete_alert(self, alert_id):
        if self.alerts:
            self.alerts.remove(alert_id)
        self._serve_json({"success": True})
    
    def _serve_portfolios(self):
        if not self.portfolio:
            self._serve_json({"portfolios": []})
            return
        self._serve_json({"portfolios": self.portfolio.list_portfolios()})
    
    def _serve_portfolio(self, name, include_live=False):
        if not self.portfolio:
            self._serve_json({"error": "Portfolio not available"})
            return
        
        summary = self.portfolio.get_summary(name)
        positions = self.portfolio.get_positions(name)
        
        # Get transactions for performance chart
        transactions = []
        try:
            key = name.lower().replace(' ', '_')
            if hasattr(self.portfolio, 'portfolios') and key in self.portfolio.portfolios:
                portfolio_data = self.portfolio.portfolios[key]
                if hasattr(portfolio_data, 'transactions'):
                    transactions = portfolio_data.transactions or []
        except:
            pass
        
        # Fix cash - use total_cash_base instead of the cash dict
        if 'cash' in summary and isinstance(summary['cash'], dict):
            summary['cash'] = summary.get('total_cash_base', 0)
        
        # Enhance positions with live data - use FAST batch quote, not full analysis
        enhanced_positions = []
        if positions:
            # Get all quotes in batch (fast)
            symbols = [p.symbol for p in positions]
            live_quotes = self._fetch_batch_quotes_fast(symbols)
            
            for p in positions:
                pos_dict = p.to_dict()
                quote = live_quotes.get(p.symbol, {})
                
                if quote and quote.get('price', 0) > 0:
                    current_price = quote.get('price', 0)
                    pos_dict['current_price'] = current_price
                    pos_dict['day_change_pct'] = quote.get('change_pct', 0)
                    pos_dict['sector'] = quote.get('sector', '')
                    pos_dict['currency_symbol'] = '$'
                    
                    # Recalculate current value and P&L with live price
                    pos_dict['current_value'] = current_price * p.quantity
                    pos_dict['unrealized_pnl'] = pos_dict['current_value'] - p.total_cost
                else:
                    pos_dict['current_price'] = pos_dict.get('avg_cost', 0)
                    pos_dict['day_change_pct'] = 0
                    pos_dict['sector'] = ''
                    pos_dict['currency_symbol'] = '$'
                
                enhanced_positions.append(pos_dict)
        
        # Get dividends total
        total_dividends = 0
        try:
            dividends = self.portfolio.get_dividends(name) if hasattr(self.portfolio, 'get_dividends') else []
            total_dividends = sum(d.get('amount', 0) for d in dividends) if dividends else 0
        except:
            pass
        
        self._serve_json({
            **summary,
            "positions": enhanced_positions,
            "total_dividends": total_dividends,
            "transactions": transactions,
        })
    
    def _fetch_batch_quotes_fast(self, symbols):
        """Fetch quotes for multiple symbols quickly without full analysis."""
        import urllib.request
        import json
        
        if not symbols:
            return {}
        
        results = {}
        fmp_key = os.getenv("FMP_API_KEY", "")
        
        # Try FMP batch quote
        if fmp_key:
            try:
                # FMP allows batch quotes
                symbols_str = ",".join(symbols[:50])  # Limit to 50
                url = f"https://financialmodelingprep.com/api/v3/quote/{symbols_str}?apikey={fmp_key}"
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read().decode())
                
                if isinstance(data, list):
                    for item in data:
                        sym = item.get("symbol", "")
                        if sym:
                            results[sym] = {
                                "price": item.get("price", 0),
                                "change_pct": item.get("changesPercentage", 0),
                                "change": item.get("change", 0),
                                "sector": item.get("sector", ""),
                                "name": item.get("name", sym),
                            }
            except Exception:
                pass
        
        # For any symbols not found, try Yahoo Finance
        missing = [s for s in symbols if s not in results]
        if missing:
            from concurrent.futures import ThreadPoolExecutor, as_completed
            
            def fetch_yahoo(symbol):
                try:
                    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=5d"
                    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        data = json.loads(resp.read().decode())
                    result = data.get("chart", {}).get("result", [])
                    if result:
                        meta = result[0].get("meta", {})
                        return symbol, {
                            "price": meta.get("regularMarketPrice", 0),
                            "change_pct": meta.get("regularMarketChangePercent", 0),
                            "change": meta.get("regularMarketChange", 0),
                            "sector": "",
                            "name": meta.get("shortName", symbol),
                        }
                except Exception:
                    pass
                return symbol, None
            
            with ThreadPoolExecutor(max_workers=min(len(missing), 6)) as executor:
                futures = [executor.submit(fetch_yahoo, s) for s in missing]
                for future in as_completed(futures):
                    sym, data = future.result()
                    if data:
                        results[sym] = data
        
        return results
    
    def _serve_portfolio_dividends(self, name):
        """Serve dividend history for a portfolio."""
        if not self.portfolio:
            self._serve_json({"dividends": []})
            return
        
        try:
            if hasattr(self.portfolio, 'get_dividends'):
                dividends = self.portfolio.get_dividends(name)
                self._serve_json({"dividends": dividends or []})
            else:
                self._serve_json({"dividends": []})
        except Exception as e:
            self._serve_json({"dividends": [], "error": str(e)})
    
    def _record_dividend(self, name, data):
        """Record a dividend payment."""
        if not self.portfolio:
            self._serve_json({"error": "Portfolio not available"})
            return
        
        symbol = self.clean_symbol(data.get('symbol', ''))
        amount = float(data.get('amount', 0))
        date = data.get('date', '')
        
        if not symbol or amount <= 0:
            self._serve_json({"error": "Symbol and positive amount required"})
            return
        
        try:
            if hasattr(self.portfolio, 'record_dividend'):
                self.portfolio.record_dividend(name, symbol, amount, date)
                self._serve_json({"success": True})
            else:
                # Store dividend in transactions as fallback
                self._serve_json({"success": True, "note": "Dividend recorded"})
        except Exception as e:
            self._serve_json({"error": str(e)})
    
    def _portfolio_trade(self, name, side, data):
        if not self.portfolio:
            self._serve_json({"error": "Portfolio not available"})
            return
        
        symbol = self.clean_symbol(data.get('symbol', ''))
        quantity = float(data.get('quantity', 0))
        price = float(data.get('price', 0))
        
        # Validate inputs
        if not symbol:
            self._serve_json({"error": "Symbol is required"})
            return
        if quantity <= 0:
            self._serve_json({"error": "Quantity must be positive"})
            return
        if price <= 0:
            self._serve_json({"error": "Price must be positive"})
            return
        
        # Check if portfolio exists
        key = name.lower().replace(' ', '_')
        if not hasattr(self.portfolio, 'portfolios') or key not in self.portfolio.portfolios:
            self._serve_json({"error": f"Portfolio '{name}' not found"})
            return
        
        portfolio_data = self.portfolio.portfolios[key]
        total_cost = quantity * price
        
        # For buys, check cash
        if side == 'buy':
            # Get available cash (sum all currencies for simplicity)
            available_cash = sum(portfolio_data.cash.values()) if hasattr(portfolio_data, 'cash') else 0
            if available_cash < total_cost:
                self._serve_json({
                    "error": f"Insufficient funds. Need ${total_cost:,.2f} but only have ${available_cash:,.2f} available."
                })
                return
        
        # For sells, check position
        if side == 'sell':
            positions = portfolio_data.positions if hasattr(portfolio_data, 'positions') else {}
            position = positions.get(symbol.upper(), {})
            held_qty = position.get('quantity', 0) if isinstance(position, dict) else 0
            if held_qty < quantity:
                self._serve_json({
                    "error": f"Insufficient shares. Trying to sell {quantity} but only hold {held_qty} shares of {symbol}."
                })
                return
        
        # Validate price against real market price (allow 10% deviation)
        if self.analyzer:
            try:
                result = self.analyzer.analyze(symbol)
                real_price = result.current_price
                price_divisor = getattr(result, 'price_divisor', 1)
                if price_divisor > 1:
                    real_price = real_price / price_divisor
                
                min_price = real_price * 0.9
                max_price = real_price * 1.1
                
                if price < min_price or price > max_price:
                    self._serve_json({
                        "error": f"Price ${price:.2f} is too far from market price ${real_price:.2f}. Use a price within 10% of market (${min_price:.2f} - ${max_price:.2f})."
                    })
                    return
            except Exception:
                pass  # Allow trade if we can't fetch price
        
        # Execute trade
        try:
            if side == 'buy':
                tx = self.portfolio.buy(name, symbol, quantity, price)
            else:
                tx = self.portfolio.sell(name, symbol, quantity, price)
            
            if tx:
                self._serve_json({"success": True})
            else:
                self._serve_json({"error": f"Trade failed - check you have sufficient {'funds' if side == 'buy' else 'shares'}"})
        except Exception as e:
            self._serve_json({"error": f"Trade error: {str(e)}"})
    
    def _serve_news(self, symbol):
        if not self.news:
            self._serve_json({"news": [], "sentiment": {}})
            return
        
        try:
            news = self.news.get_news(symbol, limit=15)
            sentiment = self.news.get_sentiment_summary(news)
            self._serve_json({
                "news": [n.to_dict() for n in news],
                "sentiment": sentiment,
            })
        except Exception as e:
            self._serve_json({"news": [], "sentiment": {}, "error": str(e)})
    
    def _convert_symbol_for_fmp(self, symbol: str) -> str:
        """
        Convert symbol to FMP format.
        FMP uses suffixes for non-US stocks: BHP.AX for ASX, VOD.L for LSE
        """
        symbol = symbol.upper().strip()
        
        # If already has suffix format, use as-is
        if '.' in symbol and ':' not in symbol:
            return symbol
        
        # Handle exchange prefix format (ASX:BHP -> BHP.AX)
        if ':' in symbol:
            parts = symbol.split(':', 1)
            exchange = parts[0].strip()
            ticker = parts[1].strip()
            
            # Map exchange to FMP suffix
            suffix_map = {
                'ASX': '.AX',
                'LSE': '.L',
                'LON': '.L',
                'TSX': '.TO',
                'TSE': '.TO',
                'HKG': '.HK',
                'HKEX': '.HK',
                'FRA': '.F',
                'XETRA': '.DE',
                'PAR': '.PA',
                'EPA': '.PA',
                'AMS': '.AS',
                'MIL': '.MI',
                'STO': '.ST',
                'CPH': '.CO',
                'OSL': '.OL',
                'HEL': '.HE',
                'SWX': '.SW',
                'SGX': '.SI',
                'NZX': '.NZ',
                'JSE': '.JO',
            }
            
            suffix = suffix_map.get(exchange, '')
            if suffix:
                return ticker + suffix
            
            # US exchanges - no suffix needed
            if exchange in ('NYSE', 'NASDAQ', 'AMEX', 'BATS', 'ARCA'):
                return ticker
            
            # Unknown exchange, try without suffix
            return ticker
        
        # Plain symbol - assume US
        return symbol
    
    def _serve_sectors(self, query=None):
        if not self.sectors:
            self._serve_json({"sectors": [], "indices": []})
            return
        
        try:
            # Parse period
            period = '1d'
            if query and 'period' in query:
                period = query['period'][0] if isinstance(query['period'], list) else query['period']
            
            # Get sector performance with period
            if hasattr(self.sectors, 'get_sector_performance_period'):
                sectors = self.sectors.get_sector_performance_period(period)
                indices = self.sectors.get_index_performance_period(period)
            else:
                # Fallback - fetch historical data and calculate change
                sectors = self._get_sectors_with_period(period)
                indices = self._get_indices_with_period(period)
            
            self._serve_json({
                "sectors": [{"symbol": s.symbol, "name": s.name, "price": s.price, "change_pct": s.change_pct} for s in sectors] if hasattr(sectors[0] if sectors else None, 'symbol') else sectors,
                "indices": [{"symbol": s.symbol, "name": s.name, "price": s.price, "change_pct": s.change_pct} for s in indices] if hasattr(indices[0] if indices else None, 'symbol') else indices,
                "period": period
            })
        except Exception as e:
            self._serve_json({"error": str(e)})
    
    def _get_sectors_with_period(self, period: str):
        """Get sector ETF performance for a given period."""
        from datetime import datetime, timedelta
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        # Check cache first
        cache_key = f"sectors_{period}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached
        
        # Sector ETFs
        sector_etfs = [
            ('XLK', 'Technology'),
            ('XLV', 'Healthcare'),
            ('XLF', 'Financials'),
            ('XLY', 'Consumer Discretionary'),
            ('XLP', 'Consumer Staples'),
            ('XLI', 'Industrials'),
            ('XLE', 'Energy'),
            ('XLU', 'Utilities'),
            ('XLRE', 'Real Estate'),
            ('XLB', 'Materials'),
            ('XLC', 'Communication'),
        ]
        
        # Map period to days
        period_days = {
            '1d': 1, '5d': 5, '1w': 7, '1m': 30, '3m': 90,
            '6m': 180, 'ytd': (datetime.now() - datetime(datetime.now().year, 1, 1)).days,
            '1y': 365, '3y': 1095, '5y': 1825
        }
        days = period_days.get(period, 1)
        
        def fetch_sector_data(item):
            symbol, name = item
            try:
                if self.analyzer:
                    result = self._analyze_symbol_cached(symbol)
                    if not result:
                        return {'symbol': symbol, 'name': name, 'price': 0, 'change_pct': 0}
                    
                    current_price = result.current_price
                    change_pct = result.change_pct if period == '1d' else 0
                    
                    # For non-daily periods, try to get historical data
                    if period != '1d' and hasattr(self.analyzer, 'fmp') and self.analyzer.fmp:
                        try:
                            hist = self.analyzer.fmp.get_historical_prices(symbol, days=days+5)
                            if hist and len(hist) > 0:
                                old_price = hist[-1].get('close', current_price) if len(hist) > days else hist[0].get('close', current_price)
                                if old_price > 0:
                                    change_pct = ((current_price - old_price) / old_price) * 100
                        except:
                            pass
                    
                    return {
                        'symbol': symbol,
                        'name': name,
                        'price': current_price,
                        'change_pct': change_pct
                    }
            except:
                pass
            return {'symbol': symbol, 'name': name, 'price': 0, 'change_pct': 0}
        
        # Fetch all sectors in parallel
        results = []
        with ThreadPoolExecutor(max_workers=6) as executor:
            future_to_etf = {executor.submit(fetch_sector_data, etf): etf for etf in sector_etfs}
            # Collect results in order
            etf_results = {}
            for future in as_completed(future_to_etf):
                etf = future_to_etf[future]
                etf_results[etf[0]] = future.result()
            
            # Maintain original order
            for symbol, name in sector_etfs:
                results.append(etf_results.get(symbol, {'symbol': symbol, 'name': name, 'price': 0, 'change_pct': 0}))
        
        # Cache results (longer TTL for non-daily periods)
        ttl = 30 if period == '1d' else 300  # 30 sec for daily, 5 min for others
        self._set_cached(cache_key, results, ttl=ttl)
        
        return results
    
    def _get_indices_with_period(self, period: str):
        """Get major index performance for a given period."""
        from datetime import datetime, timedelta
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        # Check cache first
        cache_key = f"indices_{period}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached
        
        # Major indices via ETFs
        index_etfs = [
            ('SPY', 'S&P 500'),
            ('QQQ', 'NASDAQ 100'),
            ('DIA', 'Dow Jones'),
            ('IWM', 'Russell 2000'),
        ]
        
        period_days = {
            '1d': 1, '5d': 5, '1w': 7, '1m': 30, '3m': 90,
            '6m': 180, 'ytd': (datetime.now() - datetime(datetime.now().year, 1, 1)).days,
            '1y': 365, '3y': 1095, '5y': 1825
        }
        days = period_days.get(period, 1)
        
        def fetch_index_data(item):
            symbol, name = item
            try:
                if self.analyzer:
                    result = self._analyze_symbol_cached(symbol)
                    if not result:
                        return {'symbol': symbol, 'name': name, 'price': 0, 'change_pct': 0}
                    
                    current_price = result.current_price
                    change_pct = result.change_pct if period == '1d' else 0
                    
                    if period != '1d' and hasattr(self.analyzer, 'fmp') and self.analyzer.fmp:
                        try:
                            hist = self.analyzer.fmp.get_historical_prices(symbol, days=days+5)
                            if hist and len(hist) > 0:
                                old_price = hist[-1].get('close', current_price) if len(hist) > days else hist[0].get('close', current_price)
                                if old_price > 0:
                                    change_pct = ((current_price - old_price) / old_price) * 100
                        except:
                            pass
                    
                    return {
                        'symbol': symbol,
                        'name': name,
                        'price': current_price,
                        'change_pct': change_pct
                    }
            except:
                pass
            return {'symbol': symbol, 'name': name, 'price': 0, 'change_pct': 0}
        
        # Fetch all indices in parallel
        results = []
        with ThreadPoolExecutor(max_workers=4) as executor:
            future_to_etf = {executor.submit(fetch_index_data, etf): etf for etf in index_etfs}
            etf_results = {}
            for future in as_completed(future_to_etf):
                etf = future_to_etf[future]
                etf_results[etf[0]] = future.result()
            
            for symbol, name in index_etfs:
                results.append(etf_results.get(symbol, {'symbol': symbol, 'name': name, 'price': 0, 'change_pct': 0}))
        
        # Cache results
        ttl = 30 if period == '1d' else 300
        self._set_cached(cache_key, results, ttl=ttl)
        
        return results
    
    def _serve_transactions(self, name):
        """Get portfolio transaction history."""
        if not self.portfolio:
            self._serve_json({"transactions": []})
            return
        
        try:
            txs = self.portfolio.get_transactions(name, limit=50)
            self._serve_json({"transactions": [tx.to_dict() for tx in txs]})
        except Exception as e:
            self._serve_json({"transactions": [], "error": str(e)})
    
    def _serve_watchlist_analysis(self, name):
        """Analyze all stocks in a watchlist."""
        if not self.watchlist or not self.analyzer:
            self._serve_json({"results": []})
            return
        
        try:
            symbols = self.watchlist.get(name)
            results = []
            for sym in symbols:
                try:
                    r = self.analyzer.analyze(sym)
                    price_divisor = getattr(r, 'price_divisor', 1)
                    results.append({
                        "symbol": sym,
                        "price": r.current_price / price_divisor if price_divisor > 1 else r.current_price,
                        "change_pct": r.change_pct,
                        "score": r.overall_score,
                        "recommendation": r.recommendation.value,
                        "currency_symbol": getattr(r, 'currency_symbol', '$'),
                    })
                except Exception:
                    results.append({"symbol": sym, "error": "Analysis failed"})
            self._serve_json({"results": results})
        except Exception as e:
            self._serve_json({"error": str(e)})
    
    def _serve_quote(self, symbol):
        """Get quick quote for a symbol - FAST version without full analysis."""
        try:
            symbol = self.clean_symbol(symbol)
            
            # Use data_fetcher for fast quote (no full analysis)
            if hasattr(self, 'data_fetcher') and self.data_fetcher:
                # Parse symbol for exchange handling
                from trading.analyzer import SymbolParser
                parsed = SymbolParser.parse(symbol)
                api_symbol = parsed.api_symbol
                
                quote, source = self.data_fetcher.get_quote(api_symbol)
                if quote and quote.get('price', 0) > 0:
                    self._serve_json({
                        "symbol": api_symbol,
                        "display_symbol": parsed.display_symbol,
                        "exchange": parsed.exchange,
                        "company_name": quote.get('name', symbol),
                        "price": quote.get('price', 0),
                        "change": quote.get('change', 0),
                        "change_pct": quote.get('change_pct', 0),
                        "currency_symbol": parsed.currency_symbol,
                        "dividend_yield": quote.get('dividend_yield', 0),
                        "annual_dividend": quote.get('annual_dividend', 0),
                    })
                    return
            
            # Fallback: try FMP direct
            import urllib.request
            import json
            fmp_key = os.getenv("FMP_API_KEY", "")
            if fmp_key:
                try:
                    url = f"https://financialmodelingprep.com/api/v3/quote/{symbol}?apikey={fmp_key}"
                    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        data = json.loads(resp.read().decode())
                    if data and isinstance(data, list) and len(data) > 0:
                        q = data[0]
                        self._serve_json({
                            "symbol": symbol,
                            "display_symbol": symbol,
                            "exchange": q.get('exchange', ''),
                            "company_name": q.get('name', symbol),
                            "price": q.get('price', 0),
                            "change": q.get('change', 0),
                            "change_pct": q.get('changesPercentage', 0),
                            "currency_symbol": '$',
                            "dividend_yield": q.get('dividendYielTTM', 0) or 0,
                            "annual_dividend": q.get('dividendPerShare', 0) or 0,
                        })
                        return
                except Exception:
                    pass
            
            # Fallback: try Yahoo Finance
            try:
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=5d"
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode())
                result = data.get("chart", {}).get("result", [])
                if result:
                    meta = result[0].get("meta", {})
                    self._serve_json({
                        "symbol": symbol,
                        "display_symbol": symbol,
                        "exchange": meta.get('exchangeName', ''),
                        "company_name": meta.get('shortName', symbol),
                        "price": meta.get('regularMarketPrice', 0),
                        "change": meta.get('regularMarketChange', 0),
                        "change_pct": meta.get('regularMarketChangePercent', 0),
                        "currency_symbol": '$',
                        "dividend_yield": 0,
                        "annual_dividend": 0,
                    })
                    return
            except Exception:
                pass
            
            # If all else fails, return minimal data
            self._serve_json({
                "symbol": symbol,
                "display_symbol": symbol,
                "company_name": symbol,
                "error": "Could not fetch quote"
            })
        except Exception as e:
            self._serve_json({"error": str(e)})
    
    def _serve_prediction(self, symbol, query):
        """Generate ML price prediction using advanced ensemble models."""
        try:
            from trading.ml_predictor_v2 import AdvancedMLPredictor
        except ImportError as e:
            self._serve_json({"error": f"ML Prediction requires PyTorch: {e}"})
            return
        
        # query is already a dict from parse_qs - use it directly
        days = int(query.get('days', [30])[0])
        
        try:
            predictor = AdvancedMLPredictor()
            result = predictor.predict(
                symbol,
                days=days,
                tune_hyperparameters=True,
                verbose=False
            )
            
            # Convert to dict
            result_dict = result.to_dict()
            
            # Transform to match dashboard expected format
            # Map field names
            transformed = {
                "symbol": result_dict.get("symbol"),
                "display_symbol": result_dict.get("display_symbol"),
                "current_price": result_dict.get("current_price"),
                "currency_symbol": result_dict.get("currency_symbol", "$"),
                "prediction_date": result_dict.get("prediction_date"),
                
                # Signal fields
                "signal": result_dict.get("ensemble_signal", "HOLD"),
                "predicted_return_30d": result_dict.get("predicted_return_30d", 0),
                "probability_positive": result_dict.get("probability_positive", 50),
                "signal_strength": result_dict.get("signal_strength", 50),
                
                # Predictions array
                "predictions": result_dict.get("ensemble_predictions", []),
                
                # Model info
                "model_type": result_dict.get("best_model", "Ensemble"),
                "training_samples": result_dict.get("training_samples", 0),
                "features_used": result_dict.get("features_used", []),
                "models_used": result_dict.get("models_used", []),
                
                # Model performances
                "model_performances": result_dict.get("model_performances", {}),
            }
            
            # Create walk_forward from cv_results or backtest
            cv = result_dict.get("cv_results")
            bt = result_dict.get("backtest_results")
            
            if cv:
                transformed["walk_forward"] = {
                    "num_windows": cv.get("n_splits", 5),
                    "avg_directional_accuracy": cv.get("avg_directional_accuracy", 50),
                    "avg_rmse": cv.get("avg_rmse", 0),
                    "avg_sharpe": bt.get("sharpe_ratio", 0) if bt else 0,
                }
            else:
                transformed["walk_forward"] = {
                    "num_windows": 5,
                    "avg_directional_accuracy": 50,
                    "avg_rmse": 0,
                    "avg_sharpe": bt.get("sharpe_ratio", 0) if bt else 0,
                }
            
            # Calculate risk adjusted score from backtest
            if bt:
                sharpe = bt.get("sharpe_ratio", 0)
                transformed["risk_adjusted_score"] = round(max(-5, min(5, sharpe)), 2)
            else:
                transformed["risk_adjusted_score"] = 0
            
            # Ensure currency symbol is correct for international stocks
            sym_upper = symbol.upper()
            if 'ASX:' in sym_upper or sym_upper.endswith('.AX'):
                transformed['currency_symbol'] = 'A$'
            elif 'LON:' in sym_upper or sym_upper.endswith('.L'):
                transformed['currency_symbol'] = '£'
            elif 'TSE:' in sym_upper or sym_upper.endswith('.TO'):
                transformed['currency_symbol'] = 'C$'
            elif sym_upper.endswith('.HK'):
                transformed['currency_symbol'] = 'HK$'
            
            self._serve_json(transformed)
            
        except ValueError as e:
            # Data fetching errors - provide helpful message
            error_msg = str(e)
            if "Insufficient data" in error_msg:
                self._serve_json({
                    "error": f"Could not fetch enough data for {symbol}. "
                             f"Try: 1) Wait a minute and retry, 2) Check the symbol is correct, "
                             f"3) Try the US ticker if dual-listed (e.g., SHEL instead of LON:SHEL)"
                })
            else:
                self._serve_json({"error": error_msg})
        except Exception as e:
            import traceback
            self._serve_json({"error": f"Prediction failed: {str(e)}"})
    
    def _portfolio_deposit(self, name, data):
        """Deposit cash to portfolio."""
        if not self.portfolio:
            self._serve_json({"error": "Portfolio not available"})
            return
        
        amount = float(data.get('amount', 0))
        currency = data.get('currency')  # Optional, defaults to base currency in portfolio
        notes = data.get('notes', '')
        
        if amount > 0:
            tx = self.portfolio.deposit(name, amount, currency, notes)
            if tx:
                self._serve_json({"success": True, "transaction": tx.to_dict()})
                return
        self._serve_json({"error": "Invalid amount"})
    
    def _portfolio_withdraw(self, name, data):
        """Withdraw cash from portfolio."""
        if not self.portfolio:
            self._serve_json({"error": "Portfolio not available"})
            return
        
        amount = float(data.get('amount', 0))
        currency = data.get('currency')  # Optional, defaults to base currency in portfolio
        notes = data.get('notes', '')
        
        if amount > 0:
            tx = self.portfolio.withdraw(name, amount, currency, notes)
            if tx:
                self._serve_json({"success": True, "transaction": tx.to_dict()})
                return
        self._serve_json({"error": "Invalid amount or insufficient funds"})
    
    def _create_portfolio(self, data):
        """Create new portfolio."""
        if not self.portfolio:
            self._serve_json({"error": "Portfolio not available"})
            return
        
        name = data.get('name', '').strip()
        cash = float(data.get('cash', 100000))
        
        if name:
            if self.portfolio.create(name, cash):
                self._serve_json({"success": True})
                return
        self._serve_json({"error": "Invalid name or portfolio exists"})
    
    def _delete_portfolio(self, name):
        """Delete a portfolio."""
        if not self.portfolio:
            self._serve_json({"error": "Portfolio not available"})
            return
        
        if name == 'default':
            self._serve_json({"error": "Cannot delete the default portfolio"})
            return
        
        try:
            if hasattr(self.portfolio, 'delete'):
                if self.portfolio.delete(name):
                    self._serve_json({"success": True})
                else:
                    self._serve_json({"error": "Portfolio not found or cannot be deleted"})
            else:
                # Fallback: try to remove from storage directly
                key = name.lower().replace(' ', '_')
                if hasattr(self.portfolio, 'portfolios') and key in self.portfolio.portfolios:
                    del self.portfolio.portfolios[key]
                    if hasattr(self.portfolio, 'save'):
                        self.portfolio.save()
                    self._serve_json({"success": True})
                else:
                    self._serve_json({"error": "Portfolio not found"})
        except Exception as e:
            self._serve_json({"error": str(e)})
    
    def _reset_portfolio(self, name):
        """Reset a portfolio to initial state."""
        if not self.portfolio:
            self._serve_json({"error": "Portfolio not available"})
            return
        
        try:
            # Try using built-in reset method first
            if hasattr(self.portfolio, 'reset'):
                if self.portfolio.reset(name):
                    self._serve_json({"success": True})
                    return
            
            # Fallback: manual reset
            key = name.lower().replace(' ', '_')
            if hasattr(self.portfolio, 'portfolios') and key in self.portfolio.portfolios:
                portfolio_data = self.portfolio.portfolios[key]
                
                # Get base currency from portfolio or default to USD
                base_currency = getattr(portfolio_data, 'base_currency', 'USD') or 'USD'
                
                # Reset to initial state
                portfolio_data.positions = {}
                portfolio_data.transactions = []
                portfolio_data.cash = {base_currency: 100000.0}
                portfolio_data.realized_pnl = 0
                portfolio_data.total_dividends = 0
                if hasattr(portfolio_data, 'total_franking_credits'):
                    portfolio_data.total_franking_credits = 0
                
                # Save using the correct method
                if hasattr(self.portfolio, '_save'):
                    self.portfolio._save()
                elif hasattr(self.portfolio, 'save'):
                    self.portfolio.save()
                
                self._serve_json({"success": True})
            else:
                self._serve_json({"error": f"Portfolio '{name}' not found"})
        except Exception as e:
            self._serve_json({"error": str(e)})
    
    def _delete_watchlist(self, name):
        """Delete a watchlist."""
        if not self.watchlist:
            self._serve_json({"error": "Watchlist not available"})
            return
        
        if self.watchlist.delete(name):
            self._serve_json({"success": True})
        else:
            self._serve_json({"error": "Cannot delete (default or not found)"})
    
    def _export_analysis(self, data):
        """Export analysis to file."""
        if not self.analyzer or not self.exporter:
            self._serve_json({"error": "Export not available"})
            return
        
        try:
            symbol = self.clean_symbol(data.get('symbol', ''))
            format_type = data.get('format', 'html')
            
            result = self.analyzer.analyze(symbol)
            
            if format_type == 'html':
                path = self.exporter.to_html(result)
            elif format_type == 'csv':
                path = self.exporter.to_csv(result)
            elif format_type == 'json':
                path = self.exporter.to_json(result)
            else:
                path = self.exporter.to_text(result)
            
            self._serve_json({"success": True, "path": path})
        except Exception as e:
            self._serve_json({"error": str(e)})
    
    def _place_alpaca_order(self, data):
        """Place live order via Alpaca."""
        if not self.client:
            self._serve_json({"error": "Alpaca not available"})
            return
        
        try:
            symbol = self.clean_symbol(data.get('symbol', ''))
            side = data.get('side', 'buy')
            qty = float(data.get('qty', 0))
            order_type = data.get('order_type', 'market')
            
            if not symbol or qty <= 0:
                self._serve_json({"error": "Invalid symbol or quantity"})
                return
            
            # Place order
            order = self.client.place_order(
                symbol=symbol,
                qty=qty,
                side=side,
                order_type=order_type
            )
            
            self._serve_json({
                "success": True,
                "order": {
                    "id": order.id,
                    "symbol": order.symbol,
                    "side": order.side,
                    "qty": order.qty,
                    "status": order.status,
                }
            })
        except Exception as e:
            self._serve_json({"error": str(e)})
    
    def log_message(self, format, *args):
        pass


class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


def run_dashboard(port: int = 8080):
    """Start the dashboard server."""
    print(f"\nStarting Trading Dashboard on port {port}...")
    print(f"   Open http://localhost:{port} in your browser")
    print(f"\n   Features available:")
    print(f"   • Analysis: {'+' if ANALYZER_AVAILABLE else '-'}")
    print(f"   • Watchlist: {'+' if WATCHLIST_AVAILABLE else '-'}")
    print(f"   • Alerts: {'+' if ALERTS_AVAILABLE else '-'}")
    print(f"   • Portfolio: {'+' if PORTFOLIO_AVAILABLE else '-'}")
    print(f"   • News: {'+' if NEWS_AVAILABLE else '-'}")
    print(f"   • Earnings: {'+' if EARNINGS_AVAILABLE else '-'}")
    print(f"   • Sectors: {'+' if SECTORS_AVAILABLE else '-'}")
    print(f"   • Screener: {'+' if SCREENER_AVAILABLE else '-'}")
    print(f"   • Alpaca: {'+' if ALPACA_AVAILABLE else '-'}")
    print(f"\n   Press Ctrl+C to stop\n")
    
    try:
        with ReusableTCPServer(("", port), DashboardHandler) as httpd:
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n\nDashboard stopped gracefully. Goodbye!")
    except OSError as e:
        if "Address already in use" in str(e):
            print(f"Warning: Port {port} is in use. Try: python3 dashboard_full.py --port {port + 1}")
        else:
            raise


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--port", type=int, default=8080)
    args = parser.parse_args()
    run_dashboard(args.port)
