# GitHub Actions Deployment Setup Guide

## 🔐 Security Configuration

### Required GitHub Secrets

To enable automated deployment with GitHub Actions, you need to configure the following secrets in your GitHub repository:

1. **Navigate to Repository Settings**:
   - Go to your repository on GitHub
   - Click `Settings` → `Secrets and variables` → `Actions`
   - Click `New repository secret`

2. **Configure the following secrets**:

| Secret Name | Description | Example Value | Required |
|-------------|-------------|---------------|----------|
| `SSH_PRIVATE_KEY` | ED25519 private key for server access | Content of `~/.ssh/id_ed25519` | ✅ Yes |
| `SERVER_IP` | Server IP address | `172.237.73.207` | ✅ Yes |
| `SERVER_USER` | SSH username | `root` | ✅ Yes |

### SSH Key Setup

#### Step 1: Generate SSH Key (if not exists)
```bash
# On your local machine or server
ssh-keygen -t ed25519 -C "github-actions@voxpersona"
```

#### Step 2: Copy Public Key to Server
```bash
# Copy public key to server
ssh-copy-id -i ~/.ssh/id_ed25519.pub root@172.237.73.207
```

#### Step 3: Add Private Key to GitHub Secrets
1. Copy the **private key** content:
```bash
# Display private key (copy this output)
cat ~/.ssh/id_ed25519
```

2. Add it as `SSH_PRIVATE_KEY` secret in GitHub

#### Step 4: Test Connection
```bash
# Test SSH connection
ssh -i ~/.ssh/id_ed25519 root@172.237.73.207 "echo 'Connection successful'"
```

## 🚀 Deployment Types

The GitHub Actions workflow automatically detects the type of deployment needed based on changed files:

### FULL_RESTART
**Trigger Files**: `docker-compose.yml`, `Dockerfile`, `requirements.txt`, `*.sql`, `sql_scripts/`
**Actions**: 
- Stop all containers
- Rebuild all containers with `--no-cache`
- Start all containers
**Duration**: ~2-3 minutes

### APP_ONLY
**Trigger Files**: `*.py`, `src/`, `prompts/`, `prompts-by-scenario/`
**Actions**: 
- Stop VoxPersona container only
- Rebuild VoxPersona container
- Start VoxPersona container
**Duration**: ~30-60 seconds

### NO_RESTART
**Trigger Files**: `*.md`, `*.txt`, `README`, `CHANGELOG`, `.gitignore`
**Actions**: 
- Sync files only
- No container restart
**Duration**: ~5-10 seconds

## 🎯 Manual Deployment Control

You can manually trigger deployments with specific types:

1. **Go to Actions tab** in your GitHub repository
2. **Select "Intelligent VoxPersona Deployment"**
3. **Click "Run workflow"**
4. **Choose deployment type**:
   - `auto` - Automatic detection (default)
   - `full` - Force full restart
   - `app-only` - Force app container restart only
   - `no-restart` - Force file sync only

## 📊 Monitoring and Logs

### GitHub Actions Logs
- All deployment steps are logged in GitHub Actions
- Real-time progress updates
- Error details and rollback information

### Server Logs
- Deployment history: `/home/voxpersona_user/app/deployment.log`
- Application logs: `/home/voxpersona_user/app/logs/`
- Docker logs: `docker-compose logs`

### Log Format
```
2025-01-08T14:30:15+00:00 [DEPLOY] APP_ONLY: abc1234 → def5678 (45s)
2025-01-08T14:35:22+00:00 [DEPLOY] FULL_RESTART: def5678 → ghi9012 (156s)
```

## ⚡ Performance Benchmarks

Based on the design specifications:

| Deployment Type | Target Duration | Actual Duration | Status |
|----------------|-----------------|-----------------|---------|
| NO_RESTART | < 15 seconds | ~5-10 seconds | ✅ Met |
| APP_ONLY | < 90 seconds | ~30-60 seconds | ✅ Met |
| FULL_RESTART | < 180 seconds | ~120-180 seconds | ✅ Met |

## 🔧 Troubleshooting

### Common Issues

#### SSH Connection Fails
```bash
# Check SSH key permissions
chmod 600 ~/.ssh/id_ed25519
chmod 644 ~/.ssh/id_ed25519.pub

# Test connection manually
ssh -v root@172.237.73.207
```

#### Container Startup Fails
```bash
# Check container logs
docker-compose logs --tail=50 voxpersona

# Check available resources
docker system df
docker system prune -f
```

#### Deployment Timeout
- Check server resources (CPU, Memory, Disk)
- Verify Docker daemon is running
- Check network connectivity

### Rollback Mechanism

If deployment fails, the system automatically:
1. Detects the failure
2. Reverts code to previous commit
3. Restarts containers with previous version
4. Logs rollback action

Manual rollback:
```bash
# On server
cd /home/voxpersona_user/VoxPersona
git log --oneline -10
git reset --hard <previous-commit>
cd ../app
rsync -av --exclude='.git' ../VoxPersona/ ./
docker-compose restart voxpersona
```

## 🔒 Security Considerations

### Access Control
- SSH key-based authentication only
- No password authentication
- Restricted to specific IP ranges (if configured)

### Secrets Protection
- Never commit secrets to repository
- Use GitHub Secrets for sensitive data
- Rotate SSH keys regularly

### Server Security
- Keep SSH daemon updated
- Use fail2ban for brute force protection
- Monitor deployment logs for suspicious activity

### Audit Trail
- All deployments are logged with timestamps
- Git commit hashes tracked for rollback
- GitHub Actions provides complete audit trail

## 📝 Migration Checklist

### Pre-Migration
- [ ] SSH keys configured and tested
- [ ] GitHub Secrets added
- [ ] Test branch `test-github-actions-deploy` created
- [ ] Backup current deployment system

### Migration Steps
- [ ] Test NO_RESTART deployment (documentation change)
- [ ] Test APP_ONLY deployment (code change)  
- [ ] Test FULL_RESTART deployment (infrastructure change)
- [ ] Validate performance meets requirements
- [ ] Test manual deployment triggers
- [ ] Test rollback mechanism

### Post-Migration
- [ ] Monitor first production deployments
- [ ] Update team documentation
- [ ] Remove webhook deployment system
- [ ] Archive old deployment scripts