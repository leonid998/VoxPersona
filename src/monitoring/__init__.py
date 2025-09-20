"""
VoxPersona Comprehensive Monitoring System

Provides comprehensive monitoring, metrics collection, health checks,
alerting, and observability for the VoxPersona voice analysis platform.
"""

from .metrics import (
    MonitoringSystem,
    MetricsCollector,
    SystemMonitor,
    AlertManager as MetricsAlertManager,
    get_monitoring_system,
    MetricType,
    AlertLevel,
    Metric,
    Alert as MetricsAlert
)

from .health_checks import (
    HealthStatus,
    HealthCheckResult,
    HealthCheckManager,
    DatabaseHealthCheck,
    MinIOHealthCheck,
    FileSystemHealthCheck,
    APIHealthCheck,
    quick_health_check
)

from .alerting import (
    AlertSeverity,
    AlertStatus,
    Alert,
    AlertRule,
    AlertManager,
    NotificationChannel,
    LoggingNotificationChannel,
    FileNotificationChannel,
    EmailNotificationChannel,
    WebhookNotificationChannel,
    create_alert_manager,
    quick_alert_test
)

__all__ = [
    # Original Metrics System
    'MonitoringSystem',
    'MetricsCollector', 
    'SystemMonitor',
    'MetricsAlertManager',
    'get_monitoring_system',
    'MetricType',
    'AlertLevel',
    'Metric',
    'MetricsAlert',
    
    # Health Checks
    'HealthStatus',
    'HealthCheckResult',
    'HealthCheckManager',
    'DatabaseHealthCheck',
    'MinIOHealthCheck', 
    'FileSystemHealthCheck',
    'APIHealthCheck',
    'quick_health_check',
    
    # Advanced Alerting
    'AlertSeverity',
    'AlertStatus',
    'Alert',
    'AlertRule',
    'AlertManager',
    'NotificationChannel',
    'LoggingNotificationChannel',
    'FileNotificationChannel',
    'EmailNotificationChannel',
    'WebhookNotificationChannel',
    'create_alert_manager',
    'quick_alert_test'
]

__version__ = '1.0.0'