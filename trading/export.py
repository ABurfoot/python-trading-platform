#!/usr/bin/env python3
"""
Export Reports
==============
Export analysis to PDF, CSV, and other formats.

Features:
- PDF reports (text-based, no external dependencies)
- CSV data export
- JSON export
- HTML reports
- Batch export

Usage:
    from trading.export import ReportExporter
    
    exporter = ReportExporter()
    exporter.to_csv(analysis_result, "data.csv")
    exporter.to_html(analysis_result, "report.html")
"""

import os
import json
import csv
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path


class ReportExporter:
    """Export analysis reports to various formats."""
    
    def __init__(self, output_dir: str = None):
        """
        Initialize exporter.
        
        Args:
            output_dir: Directory for output files. Defaults to ~/Documents/trading_reports
        """
        if output_dir:
            self.output_dir = Path(output_dir)
        else:
            self.output_dir = Path.home() / "Documents" / "trading_reports"
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def _serialize_object(self, obj) -> Dict:
        """Convert object to serializable dict."""
        if hasattr(obj, 'to_dict'):
            return obj.to_dict()
        elif hasattr(obj, '__dict__'):
            result = {}
            for k, v in obj.__dict__.items():
                if hasattr(v, 'value'):  # Enum
                    result[k] = v.value
                elif hasattr(v, '__dict__'):
                    result[k] = self._serialize_object(v)
                elif isinstance(v, list):
                    result[k] = [self._serialize_object(item) if hasattr(item, '__dict__') else item for item in v]
                elif isinstance(v, datetime):
                    result[k] = v.isoformat()
                else:
                    result[k] = v
            return result
        return obj
    
    def to_json(self, data: Any, filename: str = None) -> str:
        """
        Export data to JSON.
        
        Args:
            data: Data to export
            filename: Output filename (auto-generated if not provided)
        
        Returns:
            Path to created file
        """
        if filename is None:
            symbol = getattr(data, 'symbol', 'export')
            filename = f"{symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        filepath = self.output_dir / filename
        export_data = self._serialize_object(data)
        
        with open(filepath, 'w') as f:
            json.dump(export_data, f, indent=2, default=str)
        
        return str(filepath)
    
    def to_csv(self, data: Any, filename: str = None) -> str:
        """
        Export analysis to CSV.
        
        Args:
            data: AnalysisResult or dict
            filename: Output filename
        
        Returns:
            Path to created file
        """
        if filename is None:
            symbol = getattr(data, 'symbol', 'export')
            filename = f"{symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        filepath = self.output_dir / filename
        export_data = self._serialize_object(data)
        
        # Flatten nested data
        flat_data = self._flatten_dict(export_data)
        
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Metric', 'Value'])
            for key, value in flat_data.items():
                if not isinstance(value, (list, dict)):
                    writer.writerow([key, value])
        
        return str(filepath)
    
    def _flatten_dict(self, d: Dict, parent_key: str = '', sep: str = '_') -> Dict:
        """Flatten nested dict."""
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, sep).items())
            elif isinstance(v, list):
                # Skip lists for flattening
                pass
            else:
                items.append((new_key, v))
        return dict(items)
    
    def to_html(self, data: Any, filename: str = None) -> str:
        """
        Export analysis to HTML report.
        
        Args:
            data: AnalysisResult
            filename: Output filename
        
        Returns:
            Path to created file
        """
        if filename is None:
            symbol = getattr(data, 'symbol', 'export')
            filename = f"{symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        
        filepath = self.output_dir / filename
        
        # Get data
        d = self._serialize_object(data)
        
        # Build HTML
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Stock Analysis: {d.get('symbol', 'Unknown')}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
            background: #1a1a2e;
            color: #eee;
        }}
        h1 {{ color: #00d4ff; border-bottom: 2px solid #00d4ff; padding-bottom: 10px; }}
        h2 {{ color: #00d4ff; margin-top: 30px; }}
        .header {{ display: flex; justify-content: space-between; align-items: center; }}
        .price {{ font-size: 2em; font-weight: bold; }}
        .change {{ font-size: 1.2em; }}
        .positive {{ color: #00ff88; }}
        .negative {{ color: #ff4444; }}
        .neutral {{ color: #888; }}
        .card {{
            background: #16213e;
            border-radius: 10px;
            padding: 20px;
            margin: 15px 0;
        }}
        .score-bar {{
            background: #333;
            border-radius: 5px;
            height: 20px;
            overflow: hidden;
            margin: 5px 0;
        }}
        .score-fill {{
            height: 100%;
            background: linear-gradient(90deg, #ff4444, #ffaa00, #00ff88);
        }}
        .grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px; }}
        .metric {{ padding: 10px; background: #0f3460; border-radius: 5px; }}
        .metric-label {{ color: #888; font-size: 0.9em; }}
        .metric-value {{ font-size: 1.3em; font-weight: bold; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #333; }}
        th {{ color: #00d4ff; }}
        .signal-buy {{ color: #00ff88; }}
        .signal-sell {{ color: #ff4444; }}
        .signal-hold {{ color: #888; }}
        .badge {{
            display: inline-block;
            padding: 8px 20px;
            border-radius: 20px;
            font-weight: bold;
            font-size: 1.2em;
        }}
        .badge-buy {{ background: #00ff8833; color: #00ff88; }}
        .badge-sell {{ background: #ff444433; color: #ff4444; }}
        .badge-hold {{ background: #88888833; color: #888; }}
        footer {{ margin-top: 40px; color: #666; font-size: 0.9em; text-align: center; }}
    </style>
</head>
<body>
    <h1> Stock Analysis Report</h1>
    
    <div class="card">
        <div class="header">
            <div>
                <h2 style="margin:0;">{d.get('company_name', d.get('symbol', 'Unknown'))}</h2>
                <p style="color:#888;">{d.get('display_symbol', d.get('symbol', ''))} • {d.get('sector', '')} • {d.get('industry', '')}</p>
            </div>
            <div style="text-align:right;">
                <div class="price">{d.get('currency_symbol', '$')}{d.get('current_price', 0):.2f}</div>
                <div class="change {'positive' if d.get('change_pct', 0) >= 0 else 'negative'}">
                    {d.get('change', 0):+.2f} ({d.get('change_pct', 0):+.2f}%)
                </div>
            </div>
        </div>
    </div>
    
    <div class="card" style="text-align:center;">
        <h3>Recommendation</h3>
        <span class="badge {'badge-buy' if 'BUY' in str(d.get('recommendation', '')) else 'badge-sell' if 'SELL' in str(d.get('recommendation', '')) else 'badge-hold'}">
            {d.get('recommendation', 'HOLD')}
        </span>
        <p>Overall Score: <strong>{d.get('overall_score', 50):.0f}/100</strong> • Confidence: {d.get('confidence', 50):.0f}%</p>
    </div>
    
    <div class="card">
        <h3>Analysis Breakdown</h3>
        <div class="grid">
            <div class="metric">
                <div class="metric-label">Technical Score</div>
                <div class="metric-value">{d.get('technical_score', 50):.0f}/100</div>
                <div class="score-bar"><div class="score-fill" style="width:{d.get('technical_score', 50)}%"></div></div>
            </div>
            <div class="metric">
                <div class="metric-label">Fundamental Score</div>
                <div class="metric-value">{d.get('fundamental_score', 50):.0f}/100</div>
                <div class="score-bar"><div class="score-fill" style="width:{d.get('fundamental_score', 50)}%"></div></div>
            </div>
            <div class="metric">
                <div class="metric-label">Analyst Score</div>
                <div class="metric-value">{d.get('analyst_score', 50):.0f}/100</div>
                <div class="score-bar"><div class="score-fill" style="width:{d.get('analyst_score', 50)}%"></div></div>
            </div>
            <div class="metric">
                <div class="metric-label">Risk Score</div>
                <div class="metric-value">{d.get('risk_score', 50):.0f}/100</div>
                <div class="score-bar"><div class="score-fill" style="width:{d.get('risk_score', 50)}%"></div></div>
            </div>
        </div>
    </div>
    
    <div class="card">
        <h3>Key Metrics</h3>
        <div class="grid">
            <div class="metric">
                <div class="metric-label">Market Cap</div>
                <div class="metric-value">{self._format_market_cap(d.get('market_cap', 0))}</div>
            </div>
            <div class="metric">
                <div class="metric-label">P/E Ratio</div>
                <div class="metric-value">{f"{d.get('pe_ratio'):.1f}" if d.get('pe_ratio') else 'N/A'}</div>
            </div>
            <div class="metric">
                <div class="metric-label">Beta</div>
                <div class="metric-value">{d.get('beta', 1):.2f}</div>
            </div>
            <div class="metric">
                <div class="metric-label">52-Week Range</div>
                <div class="metric-value">${d.get('week_52_low', 0):.0f} - ${d.get('week_52_high', 0):.0f}</div>
            </div>
        </div>
    </div>
    
    <div class="card">
        <h3>Price Targets</h3>
        <div class="grid">
            <div class="metric">
                <div class="metric-label">Low Target</div>
                <div class="metric-value">${d.get('target_low', 0):.2f}</div>
            </div>
            <div class="metric">
                <div class="metric-label">Average Target</div>
                <div class="metric-value">${d.get('target_mid', 0):.2f}</div>
            </div>
            <div class="metric">
                <div class="metric-label">High Target</div>
                <div class="metric-value">${d.get('target_high', 0):.2f}</div>
            </div>
            <div class="metric">
                <div class="metric-label">DCF Value</div>
                <div class="metric-value">{f"${d.get('dcf_value'):.2f}" if d.get('dcf_value') else 'N/A'}</div>
            </div>
        </div>
    </div>
    
    <div class="card">
        <h3>Risk Metrics</h3>
        <table>
            <tr><td>Annual Volatility</td><td>{d.get('risk_metrics', {}).get('volatility_annual', 0):.1f}%</td></tr>
            <tr><td>VaR (95%)</td><td>{d.get('risk_metrics', {}).get('var_95', 0):.2f}%</td></tr>
            <tr><td>Max Drawdown</td><td>{d.get('risk_metrics', {}).get('max_drawdown', 0):.1f}%</td></tr>
            <tr><td>Sharpe Ratio</td><td>{d.get('risk_metrics', {}).get('sharpe_ratio', 0):.2f}</td></tr>
        </table>
    </div>
    
    <div class="card">
        <h3>Technical Signals</h3>
        <table>
            <tr><th>Indicator</th><th>Signal</th><th>Description</th></tr>
            {''.join(f"<tr><td>{s.get('name', '')}</td><td class='signal-{s.get('signal', '').lower()}'>{s.get('signal', '')}</td><td>{s.get('description', '')}</td></tr>" for s in d.get('technical_signals', [])[:7])}
        </table>
    </div>
    
    <div class="card">
        <h3>Summary</h3>
        <p>{d.get('summary', 'No summary available.')}</p>
        <h4>Key Factors:</h4>
        <ul>
            {''.join(f"<li>{f}</li>" for f in d.get('key_factors', []))}
        </ul>
    </div>
    
    <footer>
        <p>Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p>[WARN] For informational purposes only. Not financial advice.</p>
    </footer>
</body>
</html>"""
        
        with open(filepath, 'w') as f:
            f.write(html)
        
        return str(filepath)
    
    def _format_market_cap(self, mc: float) -> str:
        """Format market cap for display."""
        if mc >= 1e12:
            return f"${mc/1e12:.2f}T"
        elif mc >= 1e9:
            return f"${mc/1e9:.2f}B"
        elif mc >= 1e6:
            return f"${mc/1e6:.2f}M"
        return f"${mc:,.0f}"
    
    def to_text(self, data: Any, filename: str = None) -> str:
        """
        Export analysis to plain text report.
        
        Args:
            data: AnalysisResult
            filename: Output filename
        
        Returns:
            Path to created file
        """
        if filename is None:
            symbol = getattr(data, 'symbol', 'export')
            filename = f"{symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        filepath = self.output_dir / filename
        d = self._serialize_object(data)
        
        text = f"""
================================================================================
                         STOCK ANALYSIS REPORT
================================================================================

Company: {d.get('company_name', 'Unknown')}
Symbol:  {d.get('display_symbol', d.get('symbol', ''))}
Sector:  {d.get('sector', '')} | {d.get('industry', '')}
Date:    {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

--------------------------------------------------------------------------------
                              PRICE & CHANGE
--------------------------------------------------------------------------------

Current Price:  {d.get('currency_symbol', '$')}{d.get('current_price', 0):.2f}
Change:         {d.get('change', 0):+.2f} ({d.get('change_pct', 0):+.2f}%)
52-Week Range:  ${d.get('week_52_low', 0):.2f} - ${d.get('week_52_high', 0):.2f}

--------------------------------------------------------------------------------
                             RECOMMENDATION
--------------------------------------------------------------------------------

Signal:     {d.get('recommendation', 'HOLD')}
Score:      {d.get('overall_score', 50):.0f}/100
Confidence: {d.get('confidence', 50):.0f}%

--------------------------------------------------------------------------------
                           ANALYSIS BREAKDOWN
--------------------------------------------------------------------------------

Technical Score:    {d.get('technical_score', 50):>5.0f}/100
Fundamental Score:  {d.get('fundamental_score', 50):>5.0f}/100
Analyst Score:      {d.get('analyst_score', 50):>5.0f}/100
Risk Adjusted:      {d.get('risk_score', 50):>5.0f}/100

--------------------------------------------------------------------------------
                              KEY METRICS
--------------------------------------------------------------------------------

Market Cap:     {self._format_market_cap(d.get('market_cap', 0))}
P/E Ratio:      {d.get('pe_ratio', 0):.1f if d.get('pe_ratio') else 'N/A'}
Beta:           {d.get('beta', 1):.2f}
Trend:          {d.get('trend', 'Unknown')}

--------------------------------------------------------------------------------
                             PRICE TARGETS
--------------------------------------------------------------------------------

Analyst Low:    ${d.get('target_low', 0):.2f}
Analyst Avg:    ${d.get('target_mid', 0):.2f}
Analyst High:   ${d.get('target_high', 0):.2f}
DCF Value:      {f"${d.get('dcf_value'):.2f}" if d.get('dcf_value') else 'N/A'}

--------------------------------------------------------------------------------
                              RISK METRICS
--------------------------------------------------------------------------------

Volatility:     {d.get('risk_metrics', {}).get('volatility_annual', 0):.1f}% annual
VaR (95%):      {d.get('risk_metrics', {}).get('var_95', 0):.2f}% max daily loss
Max Drawdown:   {d.get('risk_metrics', {}).get('max_drawdown', 0):.1f}%
Sharpe Ratio:   {d.get('risk_metrics', {}).get('sharpe_ratio', 0):.2f}

--------------------------------------------------------------------------------
                               SUMMARY
--------------------------------------------------------------------------------

{d.get('summary', 'No summary available.')}

Key Factors:
{chr(10).join('  • ' + f for f in d.get('key_factors', []))}

================================================================================
[WARN]  For informational purposes only. Not financial advice.
================================================================================
"""
        
        with open(filepath, 'w') as f:
            f.write(text)
        
        return str(filepath)
    
    def batch_export(self, analyses: List[Any], format: str = "csv") -> str:
        """
        Export multiple analyses to a single file.
        
        Args:
            analyses: List of AnalysisResult objects
            format: Output format (csv, json)
        
        Returns:
            Path to created file
        """
        filename = f"batch_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{format}"
        filepath = self.output_dir / filename
        
        if format == "json":
            data = [self._serialize_object(a) for a in analyses]
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2, default=str)
        
        elif format == "csv":
            if not analyses:
                return str(filepath)
            
            # Get all keys from first analysis
            first = self._serialize_object(analyses[0])
            flat = self._flatten_dict(first)
            headers = list(flat.keys())
            
            with open(filepath, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                
                for analysis in analyses:
                    data = self._serialize_object(analysis)
                    flat = self._flatten_dict(data)
                    row = [flat.get(h, '') for h in headers]
                    writer.writerow(row)
        
        return str(filepath)


def export_analysis(analysis, format: str = "html") -> str:
    """Quick export function."""
    exporter = ReportExporter()
    
    if format == "html":
        return exporter.to_html(analysis)
    elif format == "csv":
        return exporter.to_csv(analysis)
    elif format == "json":
        return exporter.to_json(analysis)
    elif format == "txt":
        return exporter.to_text(analysis)
    else:
        raise ValueError(f"Unknown format: {format}")


# CLI
def main():
    print("Export module loaded. Use with analyzer results.")
    print("Supported formats: html, csv, json, txt")
    print(f"Output directory: {ReportExporter().output_dir}")


if __name__ == "__main__":
    main()
