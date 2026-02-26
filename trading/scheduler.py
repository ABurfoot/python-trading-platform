#!/usr/bin/env python3
"""
Scheduled Analysis Module
==========================
Automated scheduled tasks for trading analysis.

Features:
- Daily stock analysis
- Watchlist monitoring
- Alert checking
- Report generation
- Portfolio rebalancing checks
- Earnings calendar alerts

Usage:
    from trading.scheduler import TradingScheduler
    
    scheduler = TradingScheduler()
    
    # Add scheduled tasks
    scheduler.add_daily_analysis(["AAPL", "MSFT", "GOOGL"])
    scheduler.add_watchlist_monitor("default")
    scheduler.add_alert_check()
    
    # Run scheduler
    scheduler.start()
    
    # Or run manually
    scheduler.run_daily_analysis()
"""

import os
import json
import time
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Optional schedule library
try:
    import schedule
    HAS_SCHEDULE = True
except ImportError:
    HAS_SCHEDULE = False
    logger.warning("schedule library not available. Install with: pip install schedule")


class TaskFrequency(Enum):
    """Task frequency options."""
    MINUTELY = "minutely"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"


@dataclass
class ScheduledTask:
    """A scheduled task."""
    name: str
    frequency: TaskFrequency
    time: str  # HH:MM for daily, day:HH:MM for weekly
    func: Callable
    args: tuple = field(default_factory=tuple)
    kwargs: Dict = field(default_factory=dict)
    enabled: bool = True
    last_run: Optional[datetime] = None
    last_result: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "frequency": self.frequency.value,
            "time": self.time,
            "enabled": self.enabled,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "last_result": self.last_result
        }


class TradingScheduler:
    """
    Scheduler for automated trading tasks.
    
    Example:
        scheduler = TradingScheduler()
        scheduler.add_daily_analysis(["AAPL", "MSFT"])
        scheduler.start()
    """
    
    def __init__(self, data_dir: str = None):
        self.data_dir = Path(data_dir or os.path.expanduser("~/.trading_platform"))
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.reports_dir = self.data_dir / "scheduled_reports"
        self.reports_dir.mkdir(exist_ok=True)
        
        self.tasks: List[ScheduledTask] = []
        self._running = False
        self._thread: Optional[threading.Thread] = None
        
        # Load saved tasks
        self._load_tasks()
    
    def _load_tasks(self):
        """Load saved task configurations."""
        config_file = self.data_dir / "scheduler_config.json"
        if config_file.exists():
            try:
                with open(config_file) as f:
                    config = json.load(f)
                    # Tasks would need to be re-registered with functions
                    logger.info(f"Loaded scheduler config with {len(config.get('tasks', []))} saved tasks")
            except Exception as e:
                logger.error(f"Error loading scheduler config: {e}")
    
    def _save_tasks(self):
        """Save task configurations."""
        config_file = self.data_dir / "scheduler_config.json"
        try:
            config = {
                "tasks": [t.to_dict() for t in self.tasks],
                "updated": datetime.now().isoformat()
            }
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving scheduler config: {e}")
    
    def add_task(self, name: str, frequency: TaskFrequency, time: str,
                 func: Callable, *args, **kwargs) -> ScheduledTask:
        """
        Add a scheduled task.
        
        Args:
            name: Task name
            frequency: How often to run
            time: When to run (HH:MM for daily, day:HH:MM for weekly)
            func: Function to call
            *args, **kwargs: Arguments to pass to function
        """
        task = ScheduledTask(
            name=name,
            frequency=frequency,
            time=time,
            func=func,
            args=args,
            kwargs=kwargs
        )
        self.tasks.append(task)
        
        # Register with schedule library
        self._register_task(task)
        
        self._save_tasks()
        logger.info(f"Added task: {name} ({frequency.value} at {time})")
        
        return task
    
    def _register_task(self, task: ScheduledTask):
        """Register task with schedule library."""
        if not HAS_SCHEDULE:
            logger.warning(f"Cannot register task {task.name}: schedule library not installed")
            return
        
        def job_wrapper():
            if not task.enabled:
                return
            
            logger.info(f"Running task: {task.name}")
            try:
                result = task.func(*task.args, **task.kwargs)
                task.last_run = datetime.now()
                task.last_result = "success"
                logger.info(f"Task {task.name} completed successfully")
                return result
            except Exception as e:
                task.last_run = datetime.now()
                task.last_result = f"error: {str(e)}"
                logger.error(f"Task {task.name} failed: {e}")
        
        if task.frequency == TaskFrequency.MINUTELY:
            schedule.every().minute.do(job_wrapper)
        elif task.frequency == TaskFrequency.HOURLY:
            schedule.every().hour.at(f":{task.time}").do(job_wrapper)
        elif task.frequency == TaskFrequency.DAILY:
            schedule.every().day.at(task.time).do(job_wrapper)
        elif task.frequency == TaskFrequency.WEEKLY:
            day, time_str = task.time.split(":")
            getattr(schedule.every(), day.lower()).at(time_str).do(job_wrapper)
    
    def remove_task(self, name: str) -> bool:
        """Remove a task by name."""
        for i, task in enumerate(self.tasks):
            if task.name == name:
                self.tasks.pop(i)
                self._save_tasks()
                logger.info(f"Removed task: {name}")
                return True
        return False
    
    def enable_task(self, name: str, enabled: bool = True):
        """Enable or disable a task."""
        for task in self.tasks:
            if task.name == name:
                task.enabled = enabled
                self._save_tasks()
                logger.info(f"Task {name} {'enabled' if enabled else 'disabled'}")
                return True
        return False
    
    def list_tasks(self) -> List[Dict]:
        """List all scheduled tasks."""
        return [t.to_dict() for t in self.tasks]
    
    # =========================================================================
    # Pre-built Task Generators
    # =========================================================================
    
    def add_daily_analysis(self, symbols: List[str], time: str = "06:00"):
        """
        Add daily stock analysis task.
        
        Args:
            symbols: List of symbols to analyze
            time: Time to run (HH:MM)
        """
        def analyze_stocks():
            try:
                from trading.analyzer import StockAnalyzer
                from trading.export import ReportExporter
                
                analyzer = StockAnalyzer()
                exporter = ReportExporter(output_dir=str(self.reports_dir))
                
                results = []
                for symbol in symbols:
                    try:
                        result = analyzer.analyze(symbol)
                        results.append(result)
                        
                        # Export individual report
                        date_str = datetime.now().strftime("%Y%m%d")
                        exporter.to_json(result, f"{symbol}_daily_{date_str}.json")
                        
                    except Exception as e:
                        logger.error(f"Error analyzing {symbol}: {e}")
                
                # Create summary report
                self._create_daily_summary(results)
                
                return results
            except ImportError as e:
                logger.error(f"Import error in daily analysis: {e}")
                return []
        
        return self.add_task(
            name=f"daily_analysis_{'-'.join(symbols[:3])}",
            frequency=TaskFrequency.DAILY,
            time=time,
            func=analyze_stocks
        )
    
    def add_watchlist_monitor(self, watchlist_name: str = "default", 
                              time: str = "09:30"):
        """
        Add watchlist monitoring task.
        Runs at market open to check watchlist stocks.
        """
        def monitor_watchlist():
            try:
                from trading.watchlist import WatchlistManager
                from trading.analyzer import StockAnalyzer
                
                wl = WatchlistManager()
                analyzer = StockAnalyzer()
                
                symbols = wl.get(watchlist_name)
                if not symbols:
                    logger.info(f"Watchlist {watchlist_name} is empty")
                    return
                
                alerts = []
                for symbol in symbols:
                    try:
                        result = analyzer.analyze(symbol)
                        
                        # Check for significant signals
                        if result.overall_score >= 75:
                            alerts.append({
                                "symbol": symbol,
                                "type": "STRONG_BUY",
                                "score": result.overall_score,
                                "message": f"{symbol} showing strong buy signal (score: {result.overall_score})"
                            })
                        elif result.overall_score <= 25:
                            alerts.append({
                                "symbol": symbol,
                                "type": "STRONG_SELL",
                                "score": result.overall_score,
                                "message": f"{symbol} showing strong sell signal (score: {result.overall_score})"
                            })
                    except Exception as e:
                        logger.error(f"Error monitoring {symbol}: {e}")
                
                if alerts:
                    self._save_alerts(alerts)
                    logger.info(f"Generated {len(alerts)} watchlist alerts")
                
                return alerts
            except ImportError as e:
                logger.error(f"Import error in watchlist monitor: {e}")
                return []
        
        return self.add_task(
            name=f"watchlist_monitor_{watchlist_name}",
            frequency=TaskFrequency.DAILY,
            time=time,
            func=monitor_watchlist
        )
    
    def add_alert_check(self, interval_minutes: int = 5):
        """
        Add price alert checking task.
        Runs periodically during market hours.
        """
        def check_alerts():
            try:
                from trading.alerts import AlertManager
                
                alerts = AlertManager()
                triggered = alerts.check_all()
                
                if triggered:
                    logger.info(f"Triggered {len(triggered)} alerts")
                    self._save_triggered_alerts(triggered)
                
                return triggered
            except ImportError as e:
                logger.error(f"Import error in alert check: {e}")
                return []
        
        return self.add_task(
            name="alert_check",
            frequency=TaskFrequency.MINUTELY,
            time="",
            func=check_alerts
        )
    
    def add_portfolio_rebalance_check(self, portfolio_name: str = "default",
                                       time: str = "08:00", 
                                       threshold: float = 0.05):
        """
        Add weekly portfolio rebalancing check.
        """
        def check_rebalance():
            try:
                from trading.portfolio import PortfolioManager
                from trading.optimizer import PortfolioOptimizer
                
                pm = PortfolioManager()
                holdings = pm.get_holdings(portfolio_name)
                
                if not holdings:
                    logger.info(f"Portfolio {portfolio_name} has no holdings")
                    return
                
                # Get current weights
                total_value = sum(h.get("market_value", 0) for h in holdings.values())
                if total_value == 0:
                    return
                
                current_weights = {
                    sym: h.get("market_value", 0) / total_value 
                    for sym, h in holdings.items()
                }
                
                # Optimize
                symbols = list(holdings.keys())
                if len(symbols) < 2:
                    return
                
                optimizer = PortfolioOptimizer(symbols)
                recommendation = optimizer.rebalancing_recommendation(
                    current_weights, threshold
                )
                
                if recommendation["needs_rebalancing"]:
                    self._save_rebalance_recommendation(portfolio_name, recommendation)
                    logger.info(f"Rebalancing recommended for {portfolio_name}")
                
                return recommendation
            except ImportError as e:
                logger.error(f"Import error in rebalance check: {e}")
                return {}
        
        return self.add_task(
            name=f"rebalance_check_{portfolio_name}",
            frequency=TaskFrequency.WEEKLY,
            time=f"monday:{time}",
            func=check_rebalance
        )
    
    def add_earnings_alert(self, watchlist_name: str = "default", 
                           days_ahead: int = 7, time: str = "07:00"):
        """
        Add earnings calendar alert task.
        """
        def check_earnings():
            try:
                from trading.watchlist import WatchlistManager
                from trading.earnings import EarningsCalendar
                
                wl = WatchlistManager()
                ec = EarningsCalendar()
                
                symbols = wl.get(watchlist_name)
                upcoming = []
                
                for symbol in symbols:
                    try:
                        earnings = ec.get_upcoming(symbol, days=days_ahead)
                        if earnings:
                            upcoming.extend(earnings)
                    except Exception:
                        pass
                
                if upcoming:
                    self._save_earnings_alerts(upcoming)
                    logger.info(f"Found {len(upcoming)} upcoming earnings")
                
                return upcoming
            except ImportError as e:
                logger.error(f"Import error in earnings alert: {e}")
                return []
        
        return self.add_task(
            name=f"earnings_alert_{watchlist_name}",
            frequency=TaskFrequency.DAILY,
            time=time,
            func=check_earnings
        )
    
    def add_market_summary(self, time: str = "16:30"):
        """
        Add end-of-day market summary task.
        """
        def generate_summary():
            try:
                from trading.sectors import SectorAnalyzer
                
                sa = SectorAnalyzer()
                sectors = sa.get_sector_performance()
                indices = sa.get_index_performance()
                
                summary = {
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "sectors": [s.to_dict() for s in sectors],
                    "indices": [i.to_dict() for i in indices],
                    "generated": datetime.now().isoformat()
                }
                
                # Save summary
                date_str = datetime.now().strftime("%Y%m%d")
                summary_file = self.reports_dir / f"market_summary_{date_str}.json"
                with open(summary_file, 'w') as f:
                    json.dump(summary, f, indent=2)
                
                logger.info(f"Generated market summary for {date_str}")
                return summary
            except ImportError as e:
                logger.error(f"Import error in market summary: {e}")
                return {}
        
        return self.add_task(
            name="market_summary",
            frequency=TaskFrequency.DAILY,
            time=time,
            func=generate_summary
        )
    
    # =========================================================================
    # Helper Methods
    # =========================================================================
    
    def _create_daily_summary(self, results: List):
        """Create daily analysis summary."""
        if not results:
            return
        
        date_str = datetime.now().strftime("%Y%m%d")
        summary = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "symbols_analyzed": len(results),
            "strong_buys": [],
            "strong_sells": [],
            "results": []
        }
        
        for r in results:
            summary["results"].append({
                "symbol": r.symbol,
                "score": r.overall_score,
                "recommendation": r.recommendation.value if hasattr(r.recommendation, 'value') else str(r.recommendation),
                "price": r.current_price
            })
            
            if r.overall_score >= 75:
                summary["strong_buys"].append(r.symbol)
            elif r.overall_score <= 25:
                summary["strong_sells"].append(r.symbol)
        
        summary_file = self.reports_dir / f"daily_summary_{date_str}.json"
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
    
    def _save_alerts(self, alerts: List[Dict]):
        """Save generated alerts."""
        alerts_file = self.data_dir / "scheduled_alerts.json"
        
        existing = []
        if alerts_file.exists():
            try:
                with open(alerts_file) as f:
                    existing = json.load(f)
            except Exception:
                pass
        
        # Add timestamp to new alerts
        for alert in alerts:
            alert["timestamp"] = datetime.now().isoformat()
        
        existing.extend(alerts)
        
        # Keep last 100 alerts
        existing = existing[-100:]
        
        with open(alerts_file, 'w') as f:
            json.dump(existing, f, indent=2)
    
    def _save_triggered_alerts(self, triggered: List):
        """Save triggered price alerts."""
        file_path = self.data_dir / "triggered_alerts.json"
        
        existing = []
        if file_path.exists():
            try:
                with open(file_path) as f:
                    existing = json.load(f)
            except Exception:
                pass
        
        for alert in triggered:
            existing.append({
                "alert": alert.to_dict() if hasattr(alert, 'to_dict') else str(alert),
                "triggered_at": datetime.now().isoformat()
            })
        
        existing = existing[-100:]
        
        with open(file_path, 'w') as f:
            json.dump(existing, f, indent=2)
    
    def _save_rebalance_recommendation(self, portfolio: str, recommendation: Dict):
        """Save rebalancing recommendation."""
        file_path = self.reports_dir / f"rebalance_{portfolio}_{datetime.now().strftime('%Y%m%d')}.json"
        
        with open(file_path, 'w') as f:
            json.dump({
                "portfolio": portfolio,
                "date": datetime.now().isoformat(),
                "recommendation": recommendation
            }, f, indent=2)
    
    def _save_earnings_alerts(self, earnings: List):
        """Save upcoming earnings alerts."""
        file_path = self.data_dir / "earnings_alerts.json"
        
        with open(file_path, 'w') as f:
            json.dump({
                "updated": datetime.now().isoformat(),
                "upcoming": [e.to_dict() if hasattr(e, 'to_dict') else e for e in earnings]
            }, f, indent=2)
    
    # =========================================================================
    # Scheduler Control
    # =========================================================================
    
    def start(self, blocking: bool = False):
        """
        Start the scheduler.
        
        Args:
            blocking: If True, block the main thread
        """
        if self._running:
            logger.warning("Scheduler already running")
            return
        
        self._running = True
        logger.info("Starting scheduler...")
        
        if blocking:
            self._run_loop()
        else:
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()
    
    def _run_loop(self):
        """Main scheduler loop."""
        if not HAS_SCHEDULE:
            logger.error("Cannot run scheduler: schedule library not installed")
            return
        
        while self._running:
            schedule.run_pending()
            time.sleep(1)
    
    def stop(self):
        """Stop the scheduler."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Scheduler stopped")
    
    def run_task_now(self, name: str) -> Any:
        """Run a task immediately."""
        for task in self.tasks:
            if task.name == name:
                logger.info(f"Running task manually: {name}")
                try:
                    result = task.func(*task.args, **task.kwargs)
                    task.last_run = datetime.now()
                    task.last_result = "success (manual)"
                    return result
                except Exception as e:
                    task.last_run = datetime.now()
                    task.last_result = f"error: {str(e)}"
                    raise
        
        raise ValueError(f"Task not found: {name}")
    
    def run_all_now(self):
        """Run all enabled tasks immediately."""
        results = {}
        for task in self.tasks:
            if task.enabled:
                try:
                    results[task.name] = self.run_task_now(task.name)
                except Exception as e:
                    results[task.name] = f"error: {str(e)}"
        return results
    
    def get_status(self) -> Dict:
        """Get scheduler status."""
        return {
            "running": self._running,
            "schedule_available": HAS_SCHEDULE,
            "tasks": self.list_tasks(),
            "reports_dir": str(self.reports_dir),
            "next_runs": self._get_next_runs()
        }
    
    def _get_next_runs(self) -> List[Dict]:
        """Get next scheduled run times."""
        if not HAS_SCHEDULE:
            return []
        
        jobs = schedule.get_jobs()
        return [
            {
                "next_run": str(job.next_run),
                "interval": str(job.interval),
                "unit": str(job.unit)
            }
            for job in jobs
        ]
    
    def print_status(self):
        """Print scheduler status."""
        status = self.get_status()
        
        print("\n" + "="*60)
        print("TRADING SCHEDULER STATUS")
        print("="*60)
        print(f"Running: {'Yes' if status['running'] else 'No'}")
        print(f"Reports Directory: {status['reports_dir']}")
        print(f"\nTasks ({len(status['tasks'])}):")
        print("-"*60)
        
        for task in status['tasks']:
            enabled = "[OK]" if task['enabled'] else "[X]"
            last_run = task['last_run'][:19] if task['last_run'] else "Never"
            print(f"  [{enabled}] {task['name']}")
            print(f"      Frequency: {task['frequency']} at {task['time']}")
            print(f"      Last Run: {last_run} ({task['last_result'] or 'N/A'})")
        
        print("="*60)


# Convenience function for quick setup
def setup_default_scheduler(symbols: List[str] = None, 
                           watchlist: str = "default") -> TradingScheduler:
    """
    Set up scheduler with common tasks.
    
    Args:
        symbols: Symbols for daily analysis
        watchlist: Watchlist to monitor
    """
    scheduler = TradingScheduler()
    
    if symbols:
        scheduler.add_daily_analysis(symbols, time="06:00")
    
    scheduler.add_watchlist_monitor(watchlist, time="09:30")
    scheduler.add_earnings_alert(watchlist, time="07:00")
    scheduler.add_market_summary(time="16:30")
    
    return scheduler


if __name__ == "__main__":
    # Demo
    print("Trading Scheduler Demo")
    print("="*50)
    
    # Create scheduler
    scheduler = TradingScheduler()
    
    # Add some tasks
    def demo_task():
        print(f"Demo task running at {datetime.now()}")
        return "done"
    
    scheduler.add_task(
        name="demo_task",
        frequency=TaskFrequency.DAILY,
        time="10:00",
        func=demo_task
    )
    
    # Add pre-built tasks
    scheduler.add_daily_analysis(["AAPL", "MSFT", "GOOGL"], time="06:00")
    scheduler.add_watchlist_monitor("default", time="09:30")
    scheduler.add_market_summary(time="16:30")
    
    # Print status
    scheduler.print_status()
    
    print("\nTo start the scheduler:")
    print("  scheduler.start()        # Non-blocking")
    print("  scheduler.start(blocking=True)  # Blocking")
    print("\nTo run a task now:")
    print("  scheduler.run_task_now('demo_task')")
