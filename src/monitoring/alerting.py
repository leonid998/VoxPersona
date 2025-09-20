"""Comprehensive alerting system for VoxPersona monitoring.

This module provides configurable alerting with multiple notification channels,
threshold-based alerts, and intelligent alert management.
"""

import os
import time
import json
import threading
from typing import Dict, List, Optional, Any, Callable, Set
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum
from datetime import datetime, timedelta
import logging

from ..import_utils import SafeImporter
from ..config import VoxPersonaConfig
from .health_checks import HealthCheckResult, HealthStatus, HealthCheckManager


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertStatus(Enum):
    """Alert status states."""
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"


@dataclass
class Alert:
    """Represents a system alert."""
    id: str
    title: str
    description: str
    severity: AlertSeverity
    component: str
    metric: Optional[str] = None
    value: Optional[float] = None
    threshold: Optional[float] = None
    status: AlertStatus = AlertStatus.ACTIVE
    created_at: float = None
    updated_at: float = None
    resolved_at: Optional[float] = None
    acknowledged_at: Optional[float] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()
        if self.updated_at is None:
            self.updated_at = self.created_at
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert alert to dictionary."""
        return asdict(self)
    
    def age_seconds(self) -> float:
        """Get alert age in seconds."""
        return time.time() - self.created_at
    
    def is_stale(self, max_age_hours: float = 24.0) -> bool:
        """Check if alert is stale."""
        return self.age_seconds() > (max_age_hours * 3600)


class AlertRule:
    """Defines conditions for triggering alerts."""
    
    def __init__(self, 
                 name: str,
                 component: str,
                 metric: str,
                 condition: str,
                 threshold: float,
                 severity: AlertSeverity,
                 description: str = None,
                 enabled: bool = True,
                 cooldown_minutes: int = 15):
        """Initialize alert rule.
        
        Args:
            name: Rule name
            component: Component to monitor
            metric: Metric to check
            condition: Condition operator (>, <, >=, <=, ==, !=)
            threshold: Threshold value
            severity: Alert severity
            description: Rule description
            enabled: Whether rule is enabled
            cooldown_minutes: Cooldown period between alerts
        """
        self.name = name
        self.component = component
        self.metric = metric
        self.condition = condition
        self.threshold = threshold
        self.severity = severity
        self.description = description or f"{component}.{metric} {condition} {threshold}"
        self.enabled = enabled
        self.cooldown_minutes = cooldown_minutes
        self.last_triggered = 0
    
    def should_trigger(self, value: float) -> bool:
        """Check if rule should trigger based on value."""
        if not self.enabled:
            return False
        
        # Check cooldown
        if time.time() - self.last_triggered < (self.cooldown_minutes * 60):
            return False
        
        # Evaluate condition
        if self.condition == '>':
            return value > self.threshold
        elif self.condition == '<':
            return value < self.threshold
        elif self.condition == '>=':
            return value >= self.threshold
        elif self.condition == '<=':
            return value <= self.threshold
        elif self.condition == '==':
            return value == self.threshold
        elif self.condition == '!=':
            return value != self.threshold
        else:
            return False
    
    def trigger_alert(self, value: float) -> Alert:
        """Create alert from this rule."""
        self.last_triggered = time.time()
        
        alert_id = f"{self.component}_{self.metric}_{int(time.time())}"
        
        return Alert(
            id=alert_id,
            title=f"{self.component.title()} {self.metric} Alert",
            description=f"{self.description}. Current value: {value}",
            severity=self.severity,
            component=self.component,
            metric=self.metric,
            value=value,
            threshold=self.threshold,
            metadata={
                'rule_name': self.name,
                'condition': self.condition
            }
        )


class NotificationChannel:
    """Base class for notification channels."""
    
    def __init__(self, name: str, enabled: bool = True):
        self.name = name
        self.enabled = enabled
        self.logger = logging.getLogger(f"{__name__}.{name}")
    
    def send_alert(self, alert: Alert) -> bool:
        """Send alert notification. Override in subclasses."""
        raise NotImplementedError("Subclasses must implement send_alert")
    
    def test_connection(self) -> bool:
        """Test notification channel. Override in subclasses."""
        return True


class LoggingNotificationChannel(NotificationChannel):
    """Notification channel that logs alerts."""
    
    def __init__(self, log_level: str = "ERROR"):
        super().__init__("logging")
        self.log_level = getattr(logging, log_level.upper(), logging.ERROR)
    
    def send_alert(self, alert: Alert) -> bool:
        """Log alert notification."""
        try:
            message = f"[{alert.severity.value.upper()}] {alert.title}: {alert.description}"
            self.logger.log(self.log_level, message)
            return True
        except Exception as e:
            self.logger.error(f"Failed to log alert: {e}")
            return False


class FileNotificationChannel(NotificationChannel):
    """Notification channel that writes alerts to file."""
    
    def __init__(self, file_path: str):
        super().__init__("file")
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
    
    def send_alert(self, alert: Alert) -> bool:
        """Write alert to file."""
        try:
            alert_data = {
                'timestamp': datetime.fromtimestamp(alert.created_at).isoformat(),
                'alert': alert.to_dict()
            }
            
            with open(self.file_path, 'a') as f:
                f.write(json.dumps(alert_data) + '\n')
            
            return True
        except Exception as e:
            self.logger.error(f"Failed to write alert to file: {e}")
            return False


class EmailNotificationChannel(NotificationChannel):
    """Email notification channel."""
    
    def __init__(self, smtp_config: Dict[str, Any], recipients: List[str]):
        super().__init__("email")
        self.smtp_config = smtp_config
        self.recipients = recipients
        self.importer = SafeImporter()
    
    def send_alert(self, alert: Alert) -> bool:
        """Send alert via email."""
        # Import email modules
        smtplib = self.importer.safe_import('smtplib')
        email_mime = self.importer.safe_import('email.mime.text')
        
        if not hasattr(smtplib, 'SMTP') or not hasattr(email_mime, 'MIMEText'):
            self.logger.warning("Email modules not available")
            return False
        
        try:
            # Create message
            subject = f"[VoxPersona] {alert.severity.value.upper()}: {alert.title}"
            body = self._format_email_body(alert)
            
            msg = email_mime.MIMEText(body)
            msg['Subject'] = subject
            msg['From'] = self.smtp_config.get('from_address', 'voxpersona@localhost')
            msg['To'] = ', '.join(self.recipients)
            
            # Send email
            with smtplib.SMTP(
                self.smtp_config.get('host', 'localhost'),
                self.smtp_config.get('port', 587)
            ) as server:
                if self.smtp_config.get('use_tls', True):
                    server.starttls()
                
                if 'username' in self.smtp_config:
                    server.login(
                        self.smtp_config['username'],
                        self.smtp_config['password']
                    )
                
                server.send_message(msg, to_addrs=self.recipients)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send email alert: {e}")
            return False
    
    def _format_email_body(self, alert: Alert) -> str:
        """Format email body for alert."""
        return f"""
VoxPersona Alert Notification

Alert ID: {alert.id}
Severity: {alert.severity.value.upper()}
Component: {alert.component}
Time: {datetime.fromtimestamp(alert.created_at).strftime('%Y-%m-%d %H:%M:%S')}

Description:
{alert.description}

Metric: {alert.metric or 'N/A'}
Current Value: {alert.value or 'N/A'}
Threshold: {alert.threshold or 'N/A'}

Status: {alert.status.value}

This is an automated message from VoxPersona monitoring system.
"""
    
    def test_connection(self) -> bool:
        """Test SMTP connection."""
        smtplib = self.importer.safe_import('smtplib')
        
        if not hasattr(smtplib, 'SMTP'):
            return False
        
        try:
            with smtplib.SMTP(
                self.smtp_config.get('host', 'localhost'),
                self.smtp_config.get('port', 587),
                timeout=10
            ) as server:
                if self.smtp_config.get('use_tls', True):
                    server.starttls()
                return True
        except Exception:
            return False


class WebhookNotificationChannel(NotificationChannel):
    """Webhook notification channel."""
    
    def __init__(self, webhook_url: str, headers: Dict[str, str] = None):
        super().__init__("webhook")
        self.webhook_url = webhook_url
        self.headers = headers or {'Content-Type': 'application/json'}
        self.importer = SafeImporter()
    
    def send_alert(self, alert: Alert) -> bool:
        """Send alert via webhook."""
        requests = self.importer.safe_import('requests')
        
        if not hasattr(requests, 'post'):
            self.logger.warning("HTTP client not available")
            return False
        
        try:
            payload = {
                'alert': alert.to_dict(),
                'timestamp': datetime.fromtimestamp(alert.created_at).isoformat(),
                'source': 'voxpersona-monitoring'
            }
            
            response = requests.post(
                self.webhook_url,
                json=payload,
                headers=self.headers,
                timeout=10
            )
            
            response.raise_for_status()
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send webhook alert: {e}")
            return False
    
    def test_connection(self) -> bool:
        """Test webhook endpoint."""
        requests = self.importer.safe_import('requests')
        
        if not hasattr(requests, 'get'):
            return False
        
        try:
            # Try a simple GET request to the webhook URL
            response = requests.get(self.webhook_url, timeout=5)
            return response.status_code < 500
        except Exception:
            return False


class AlertManager:
    """Main alert management system."""
    
    def __init__(self, config: Optional[VoxPersonaConfig] = None):
        """Initialize alert manager.
        
        Args:
            config: VoxPersona configuration instance
        """
        self.config = config or VoxPersonaConfig()
        self.logger = logging.getLogger(__name__)
        
        # Alert storage
        self._active_alerts: Dict[str, Alert] = {}
        self._alert_history: List[Alert] = []
        self._alert_lock = threading.Lock()
        
        # Rules and channels
        self._rules: List[AlertRule] = []
        self._notification_channels: List[NotificationChannel] = []
        
        # Health check integration
        self._health_manager = HealthCheckManager(config)
        
        # Initialize default configuration
        self._setup_default_rules()
        self._setup_default_channels()
        
        # Background monitoring
        self._monitoring_thread = None
        self._monitoring_active = False
    
    def _setup_default_rules(self):
        """Setup default alert rules."""
        default_rules = [
            # Health check rules
            AlertRule(
                name="component_critical",
                component="health",
                metric="status",
                condition="==",
                threshold=0,  # 0 = critical
                severity=AlertSeverity.CRITICAL,
                description="System component is in critical state",
                cooldown_minutes=5
            ),
            
            # Performance rules
            AlertRule(
                name="high_response_time",
                component="health",
                metric="response_time",
                condition=">",
                threshold=5.0,
                severity=AlertSeverity.WARNING,
                description="Component response time is high",
                cooldown_minutes=10
            ),
            
            # Disk space rules
            AlertRule(
                name="low_disk_space",
                component="filesystem",
                metric="free_gb",
                condition="<",
                threshold=1.0,
                severity=AlertSeverity.ERROR,
                description="Low disk space warning",
                cooldown_minutes=30
            ),
            
            AlertRule(
                name="critical_disk_space",
                component="filesystem",
                metric="free_gb",
                condition="<",
                threshold=0.5,
                severity=AlertSeverity.CRITICAL,
                description="Critical disk space alert",
                cooldown_minutes=15
            )
        ]
        
        self._rules.extend(default_rules)
    
    def _setup_default_channels(self):
        """Setup default notification channels."""
        # Always add logging channel
        self._notification_channels.append(LoggingNotificationChannel())
        
        # Add file channel for alerts
        alert_config = self.config.get_alert_config()
        if alert_config and alert_config.get('file_alerts', True):
            alerts_file = Path(self.config.get_logs_path()) / "alerts.jsonl"
            self._notification_channels.append(FileNotificationChannel(str(alerts_file)))
        
        # Add email channel if configured
        if alert_config and 'email' in alert_config:
            email_config = alert_config['email']
            if email_config.get('enabled', False):
                self._notification_channels.append(EmailNotificationChannel(
                    smtp_config=email_config.get('smtp', {}),
                    recipients=email_config.get('recipients', [])
                ))
        
        # Add webhook channel if configured
        if alert_config and 'webhook' in alert_config:
            webhook_config = alert_config['webhook']
            if webhook_config.get('enabled', False):
                self._notification_channels.append(WebhookNotificationChannel(
                    webhook_url=webhook_config['url'],
                    headers=webhook_config.get('headers', {})
                ))
    
    def add_rule(self, rule: AlertRule):
        """Add alert rule."""
        with self._alert_lock:
            self._rules.append(rule)
            self.logger.info(f"Added alert rule: {rule.name}")
    
    def remove_rule(self, rule_name: str) -> bool:
        """Remove alert rule by name."""
        with self._alert_lock:
            for i, rule in enumerate(self._rules):
                if rule.name == rule_name:
                    del self._rules[i]
                    self.logger.info(f"Removed alert rule: {rule_name}")
                    return True
            return False
    
    def add_notification_channel(self, channel: NotificationChannel):
        """Add notification channel."""
        self._notification_channels.append(channel)
        self.logger.info(f"Added notification channel: {channel.name}")
    
    def trigger_alert(self, alert: Alert) -> bool:
        """Manually trigger an alert."""
        with self._alert_lock:
            # Check if similar alert already exists
            existing_alert = self._find_similar_alert(alert)
            
            if existing_alert:
                # Update existing alert
                existing_alert.updated_at = time.time()
                existing_alert.value = alert.value
                self.logger.debug(f"Updated existing alert: {existing_alert.id}")
                return True
            
            # Add new alert
            self._active_alerts[alert.id] = alert
            self._alert_history.append(alert)
            
            self.logger.info(f"Triggered alert: {alert.title}")
            
            # Send notifications
            self._send_notifications(alert)
            
            return True
    
    def _find_similar_alert(self, alert: Alert) -> Optional[Alert]:
        """Find similar active alert."""
        for existing_alert in self._active_alerts.values():
            if (existing_alert.component == alert.component and
                existing_alert.metric == alert.metric and
                existing_alert.status == AlertStatus.ACTIVE):
                return existing_alert
        return None
    
    def _send_notifications(self, alert: Alert):
        """Send alert notifications through all channels."""
        for channel in self._notification_channels:
            if not channel.enabled:
                continue
            
            try:
                success = channel.send_alert(alert)
                if success:
                    self.logger.debug(f"Sent alert {alert.id} via {channel.name}")
                else:
                    self.logger.warning(f"Failed to send alert {alert.id} via {channel.name}")
            except Exception as e:
                self.logger.error(f"Error sending alert via {channel.name}: {e}")
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert."""
        with self._alert_lock:
            if alert_id in self._active_alerts:
                alert = self._active_alerts[alert_id]
                alert.status = AlertStatus.ACKNOWLEDGED
                alert.acknowledged_at = time.time()
                alert.updated_at = time.time()
                self.logger.info(f"Acknowledged alert: {alert_id}")
                return True
            return False
    
    def resolve_alert(self, alert_id: str) -> bool:
        """Resolve an alert."""
        with self._alert_lock:
            if alert_id in self._active_alerts:
                alert = self._active_alerts[alert_id]
                alert.status = AlertStatus.RESOLVED
                alert.resolved_at = time.time()
                alert.updated_at = time.time()
                
                # Remove from active alerts
                del self._active_alerts[alert_id]
                
                self.logger.info(f"Resolved alert: {alert_id}")
                return True
            return False
    
    def get_active_alerts(self) -> List[Alert]:
        """Get all active alerts."""
        with self._alert_lock:
            return list(self._active_alerts.values())
    
    def get_alert_history(self, limit: int = 100) -> List[Alert]:
        """Get alert history."""
        with self._alert_lock:
            return self._alert_history[-limit:]
    
    def start_monitoring(self, interval_seconds: int = 60):
        """Start background monitoring."""
        if self._monitoring_active:
            return
        
        self._monitoring_active = True
        self._monitoring_thread = threading.Thread(
            target=self._monitoring_loop,
            args=(interval_seconds,),
            daemon=True
        )
        self._monitoring_thread.start()
        self.logger.info("Started alert monitoring")
    
    def stop_monitoring(self):
        """Stop background monitoring."""
        self._monitoring_active = False
        if self._monitoring_thread:
            self._monitoring_thread.join(timeout=5)
        self.logger.info("Stopped alert monitoring")
    
    def _monitoring_loop(self, interval_seconds: int):
        """Background monitoring loop."""
        while self._monitoring_active:
            try:
                self._check_health_alerts()
                self._cleanup_stale_alerts()
                time.sleep(interval_seconds)
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                time.sleep(interval_seconds)
    
    def _check_health_alerts(self):
        """Check health status and trigger alerts if needed."""
        try:
            health_results = self._health_manager.run_all_checks()
            
            for component_name, result in health_results.items():
                # Check status-based rules
                status_value = 0 if result.status == HealthStatus.CRITICAL else (
                    1 if result.status == HealthStatus.WARNING else 2
                )
                
                self._evaluate_rules(component_name, "status", status_value)
                
                # Check response time rules
                if result.response_time > 0:
                    self._evaluate_rules(component_name, "response_time", result.response_time)
                
                # Check component-specific metrics
                if 'checks' in result.details:
                    checks = result.details['checks']
                    
                    # File system metrics
                    if component_name == 'filesystem' and 'disk_space' in checks:
                        disk_space = checks['disk_space']
                        if 'free_gb' in disk_space and isinstance(disk_space['free_gb'], (int, float)):
                            self._evaluate_rules('filesystem', 'free_gb', disk_space['free_gb'])
                            
        except Exception as e:
            self.logger.error(f"Error checking health alerts: {e}")
    
    def _evaluate_rules(self, component: str, metric: str, value: float):
        """Evaluate alert rules for given metric."""
        for rule in self._rules:
            if rule.component == component and rule.metric == metric:
                if rule.should_trigger(value):
                    alert = rule.trigger_alert(value)
                    self.trigger_alert(alert)
    
    def _cleanup_stale_alerts(self):
        """Clean up stale alerts."""
        with self._alert_lock:
            current_time = time.time()
            stale_alert_ids = []
            
            for alert_id, alert in self._active_alerts.items():
                if alert.is_stale():
                    stale_alert_ids.append(alert_id)
            
            for alert_id in stale_alert_ids:
                alert = self._active_alerts[alert_id]
                alert.status = AlertStatus.RESOLVED
                alert.resolved_at = current_time
                alert.updated_at = current_time
                del self._active_alerts[alert_id]
                
                self.logger.info(f"Auto-resolved stale alert: {alert_id}")
    
    def get_alert_summary(self) -> Dict[str, Any]:
        """Get alert system summary."""
        with self._alert_lock:
            active_alerts = list(self._active_alerts.values())
            
            severity_counts = {severity.value: 0 for severity in AlertSeverity}
            for alert in active_alerts:
                severity_counts[alert.severity.value] += 1
            
            return {
                'total_active_alerts': len(active_alerts),
                'severity_breakdown': severity_counts,
                'total_rules': len(self._rules),
                'enabled_rules': len([r for r in self._rules if r.enabled]),
                'notification_channels': len(self._notification_channels),
                'enabled_channels': len([c for c in self._notification_channels if c.enabled]),
                'monitoring_active': self._monitoring_active,
                'recent_alerts': len([a for a in active_alerts if a.age_seconds() < 3600])
            }
    
    def test_notifications(self) -> Dict[str, bool]:
        """Test all notification channels."""
        test_alert = Alert(
            id="test_alert",
            title="Test Alert",
            description="This is a test alert to verify notification channels",
            severity=AlertSeverity.INFO,
            component="test"
        )
        
        results = {}
        for channel in self._notification_channels:
            if channel.enabled:
                try:
                    results[channel.name] = channel.send_alert(test_alert)
                except Exception as e:
                    self.logger.error(f"Error testing {channel.name}: {e}")
                    results[channel.name] = False
            else:
                results[channel.name] = False
        
        return results


# Convenience functions
def create_alert_manager(config: Optional[VoxPersonaConfig] = None) -> AlertManager:
    """Create and configure alert manager."""
    return AlertManager(config)


def quick_alert_test(config: Optional[VoxPersonaConfig] = None) -> Dict[str, Any]:
    """Quick test of alert system."""
    manager = AlertManager(config)
    
    # Test notifications
    notification_results = manager.test_notifications()
    
    # Get summary
    summary = manager.get_alert_summary()
    
    return {
        'alert_summary': summary,
        'notification_test_results': notification_results
    }


if __name__ == '__main__':
    # Example usage
    print("Testing VoxPersona alert system...")
    
    test_results = quick_alert_test()
    
    print(f"Active alerts: {test_results['alert_summary']['total_active_alerts']}")
    print(f"Alert rules: {test_results['alert_summary']['total_rules']}")
    print(f"Notification channels: {test_results['alert_summary']['notification_channels']}")
    
    print("\nNotification test results:")
    for channel, success in test_results['notification_test_results'].items():
        status = "✓" if success else "✗"
        print(f"  {status} {channel}")