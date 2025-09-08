# GitHub Integration Documentation

This directory contains all GitHub-specific configuration and documentation for VoxPersona's deployment and CI/CD systems.

## 📁 Directory Structure

```
.github/
├── workflows/
│   ├── deploy.yml              # Intelligent deployment workflow
│   ├── deploy.yml.disabled     # Legacy deployment (backup)
│   └── python-app.yml          # Python testing workflow
├── DEPLOYMENT_SETUP.md         # SSH keys, secrets, configuration guide
├── TESTING_GUIDE.md            # Comprehensive testing scenarios
├── MIGRATION_GUIDE.md          # Webhook to GitHub Actions migration
└── README.md                   # This file
```

## 🚀 Deployment System

VoxPersona uses an intelligent GitHub Actions deployment system that automatically determines the optimal deployment strategy:

- **NO_RESTART** (5-10s): Documentation changes only
- **APP_ONLY** (30-60s): Application code changes  
- **FULL_RESTART** (2-3min): Infrastructure changes

### Quick Start
1. Configure GitHub Secrets (see [DEPLOYMENT_SETUP.md](DEPLOYMENT_SETUP.md))
2. Push to main branch
3. Monitor deployment in GitHub Actions

## 📚 Documentation Guide

### For Developers
- **Start here**: [DEPLOYMENT_SETUP.md](DEPLOYMENT_SETUP.md)
- **Testing**: [TESTING_GUIDE.md](TESTING_GUIDE.md)

### For DevOps/Admins
- **Migration**: [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md)
- **Workflow Config**: [workflows/deploy.yml](workflows/deploy.yml)

### For Project Managers
- **Benefits**: See migration benefits in [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md#-migration-benefits)
- **Timeline**: [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md#-migration-timeline)

## 🔧 Workflow Files

### deploy.yml
The main deployment workflow with intelligent restart logic:
- Automatic deployment type detection
- SSH-based deployment to production server
- Health checks and rollback mechanisms
- Performance monitoring and logging

### python-app.yml  
Python application testing workflow:
- Code quality checks
- Unit test execution
- Dependency vulnerability scanning

### deploy.yml.disabled
Legacy deployment configuration (backup):
- Simple SSH deployment without intelligent logic
- Kept for emergency rollback scenarios

## 🔐 Security Configuration

Required GitHub Secrets:
- `SSH_PRIVATE_KEY`: ED25519 private key for server access
- `SERVER_IP`: Production server IP address  
- `SERVER_USER`: SSH username for deployment

See [DEPLOYMENT_SETUP.md](DEPLOYMENT_SETUP.md#-security-configuration) for detailed setup.

## 📊 Performance Benchmarks

| Deployment Type | Target Time | Typical Range |
|-----------------|-------------|---------------|
| NO_RESTART      | < 15s       | 5-10s        |
| APP_ONLY        | < 90s       | 30-60s       |
| FULL_RESTART    | < 180s      | 120-180s     |

## 🎯 Manual Deployment

Trigger manual deployments:
1. Go to Actions → "Intelligent VoxPersona Deployment"
2. Click "Run workflow"  
3. Select branch and deployment type
4. Monitor execution

## 🚨 Troubleshooting

### Common Issues
- **SSH Connection Failed**: Check SSH keys and server access
- **Deployment Timeout**: Verify server resources and Docker status
- **Container Startup Failed**: Review application logs and configuration

### Support Resources
1. GitHub Actions execution logs
2. Server deployment logs: `/home/voxpersona_user/app/deployment.log`
3. Docker logs: `docker-compose logs`
4. [TESTING_GUIDE.md](TESTING_GUIDE.md#troubleshooting) for detailed debugging

## 📈 Deployment Analytics

Monitor deployment metrics:
- Deployment frequency and success rate
- Performance trends by deployment type
- Error patterns and resolution time
- Team productivity improvements

## 🔄 Continuous Improvement

This deployment system evolves based on:
- Performance monitoring data
- Team feedback and usage patterns
- Security audit recommendations
- Infrastructure optimization opportunities

---

**Last Updated**: Implementation of intelligent deployment system
**Next Review**: Performance optimization and monitoring enhancement