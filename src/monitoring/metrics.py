"""
Monitoring System for VoxPersona - Metrics Collection and Alerting
"""

import logging
import time
import threading
from typing import Dict, Any, List
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta
from collections import defaultdict, deque
import psutil

logger = logging.getLogger(__name__)


class MetricType(Enum):
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"


class AlertLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class Metric:
    name: str
    value: float
    metric_type: MetricType
    timestamp: datetime
    tags: Dict[str, str] = None


@dataclass
class Alert:
    component: str
    level: AlertLevel
    message: str
    timestamp: datetime


class MetricsCollector:
    def __init__(self):
        self.metrics = defaultdict(lambda: deque(maxlen=1000))
        self._lock = threading.Lock()
    
    def record_metric(self, name: str, value: float, tags: Dict[str, str] = None):
        metric = Metric(name, value, MetricType.GAUGE, datetime.now(), tags)
        with self._lock:
            self.metrics[name].append(metric)
    
    def get_metric_history(self, name: str, duration: timedelta = None) -> List[Metric]:
        with self._lock:
            if name not in self.metrics:
                return []
            metrics = list(self.metrics[name])
        
        if duration:
            cutoff = datetime.now() - duration
            metrics = [m for m in metrics if m.timestamp >= cutoff]
        return metrics


class SystemMonitor:
    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics = metrics_collector
        self.monitoring_active = False
        self.monitor_thread = None
    
    def start_monitoring(self):
        if self.monitoring_active:
            return
        self.monitoring_active = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
    
    def stop_monitoring(self):
        self.monitoring_active = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
    
    def _monitor_loop(self):
        while self.monitoring_active:
            try:
                # Collect system metrics
                self.metrics.record_metric('system.cpu.usage', psutil.cpu_percent())
                self.metrics.record_metric('system.memory.usage', psutil.virtual_memory().percent)
                time.sleep(30)
            except Exception as e:
                logger.error(f"System monitoring error: {e}")
                time.sleep(30)


class AlertManager:
    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics = metrics_collector
        self.alerts = []
        self.alert_rules = []
        self.monitoring_active = False
        self.monitor_thread = None
    
    def add_alert_rule(self, metric_name: str, threshold: float, level: AlertLevel, message: str):
        self.alert_rules.append({
            'metric': metric_name,
            'threshold': threshold,
            'level': level,
            'message': message
        })
    
    def start_monitoring(self):
        if self.monitoring_active:
            return
        self.monitoring_active = True
        self.monitor_thread = threading.Thread(target=self._alert_loop, daemon=True)
        self.monitor_thread.start()
    
    def stop_monitoring(self):
        self.monitoring_active = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
    
    def _alert_loop(self):
        while self.monitoring_active:
            try:
                self._check_alerts()
                time.sleep(60)
            except Exception as e:
                logger.error(f"Alert monitoring error: {e}")
                time.sleep(60)
    
    def _check_alerts(self):
        for rule in self.alert_rules:
            metrics = self.metrics.get_metric_history(rule['metric'], timedelta(minutes=5))
            if metrics and metrics[-1].value > rule['threshold']:
                alert = Alert(rule['metric'], rule['level'], rule['message'], datetime.now())
                self.alerts.append(alert)
                logger.warning(f"Alert: {alert.message}")


class MonitoringSystem:
    def __init__(self):
        self.metrics_collector = MetricsCollector()
        self.system_monitor = SystemMonitor(self.metrics_collector)
        self.alert_manager = AlertManager(self.metrics_collector)
        
        # Setup default alerts
        self.alert_manager.add_alert_rule('system.cpu.usage', 90.0, AlertLevel.WARNING, 'High CPU usage')
        self.alert_manager.add_alert_rule('system.memory.usage', 95.0, AlertLevel.CRITICAL, 'Critical memory usage')
    
    def start(self):
        logger.info("Starting monitoring system")
        self.system_monitor.start_monitoring()
        self.alert_manager.start_monitoring()
    
    def stop(self):
        logger.info("Stopping monitoring system")
        self.system_monitor.stop_monitoring()
        self.alert_manager.stop_monitoring()
    
    def get_status(self) -> Dict[str, Any]:
        return {
            'timestamp': datetime.now().isoformat(),
            'active_alerts': len([a for a in self.alert_manager.alerts if (datetime.now() - a.timestamp).seconds < 3600]),
            'monitoring_active': self.system_monitor.monitoring_active
        }


# Global instance
_monitoring_system = None

def get_monitoring_system():
    global _monitoring_system
    if _monitoring_system is None:
        _monitoring_system = MonitoringSystem()
    return _monitoring_system