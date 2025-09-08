# GitHub Actions Deployment Testing Guide

## 🧪 Test Scenarios

This guide provides comprehensive test scenarios to validate the GitHub Actions deployment workflow before production use.

## Prerequisites

1. **Test branch created**: `test-github-actions-deploy`
2. **GitHub Secrets configured**:
   - `SSH_PRIVATE_KEY`
   - `SERVER_IP` 
   - `SERVER_USER`
3. **SSH access verified** to deployment server

## Test Execution Plan

### Phase 1: Documentation Changes (NO_RESTART)

#### Test Case 1.1: README Update
**Objective**: Verify NO_RESTART detection for documentation changes

```bash
# Create test change
echo "## Test Update $(date)" >> README.md
git add README.md
git commit -m "Test: Update README for NO_RESTART validation"
git push origin test-github-actions-deploy
```

**Expected Results**:
- ✅ Deployment type detected: `NO_RESTART`
- ✅ Files synced to server
- ✅ No containers restarted
- ✅ Duration: < 15 seconds
- ✅ Health checks skipped appropriately

#### Test Case 1.2: Multiple Documentation Files
```bash
# Create multiple documentation changes
echo "# Test Guide Update" >> DEPLOYMENT_GUIDE.md
echo "# Setup Update" >> SETUP.md
touch CHANGELOG.md
echo "## Version 1.0.1" > CHANGELOG.md

git add .
git commit -m "Test: Multiple documentation updates"
git push origin test-github-actions-deploy
```

**Expected Results**:
- ✅ Deployment type: `NO_RESTART`
- ✅ All files synced correctly
- ✅ Duration: < 15 seconds

### Phase 2: Application Changes (APP_ONLY)

#### Test Case 2.1: Python Code Change
**Objective**: Verify APP_ONLY detection for source code changes

```bash
# Create test Python file change
echo "# Test comment $(date)" >> src/config.py
git add src/config.py
git commit -m "Test: Python code change for APP_ONLY validation"
git push origin test-github-actions-deploy
```

**Expected Results**:
- ✅ Deployment type detected: `APP_ONLY`
- ✅ VoxPersona container stopped and rebuilt
- ✅ PostgreSQL container remains running
- ✅ Duration: 30-90 seconds
- ✅ Health checks pass
- ✅ Application configuration loads successfully

#### Test Case 2.2: Prompts Update
```bash
# Update prompt files
echo "# Additional prompt context" >> prompts/interview_methodology.txt
mkdir -p prompts-by-scenario/test
echo "Test prompt" > prompts-by-scenario/test/test_prompt.txt

git add prompts/ prompts-by-scenario/
git commit -m "Test: Prompt files update for APP_ONLY validation"
git push origin test-github-actions-deploy
```

**Expected Results**:
- ✅ Deployment type: `APP_ONLY`
- ✅ Prompt files synced correctly
- ✅ Only app container restarted

#### Test Case 2.3: Mixed Changes (Code + Documentation)
```bash
# Mixed changes - should trigger APP_ONLY
echo "# Code change $(date)" >> src/bot.py
echo "# Doc change $(date)" >> README.md

git add .
git commit -m "Test: Mixed code and documentation changes"
git push origin test-github-actions-deploy
```

**Expected Results**:
- ✅ Deployment type: `APP_ONLY` (code takes precedence)
- ✅ All files synced
- ✅ App container restarted

### Phase 3: Infrastructure Changes (FULL_RESTART)

#### Test Case 3.1: Docker Compose Change
**Objective**: Verify FULL_RESTART detection for infrastructure changes

```bash
# Add comment to docker-compose.yml
echo "# Test infrastructure change - $(date)" >> docker-compose.yml
git add docker-compose.yml
git commit -m "Test: Docker compose change for FULL_RESTART validation"
git push origin test-github-actions-deploy
```

**Expected Results**:
- ✅ Deployment type detected: `FULL_RESTART`
- ✅ All containers stopped
- ✅ All containers rebuilt with `--no-cache`
- ✅ All containers restarted
- ✅ Duration: 120-180 seconds
- ✅ Both VoxPersona and PostgreSQL containers healthy
- ✅ Application configuration loads successfully

#### Test Case 3.2: Requirements Change
```bash
# Add comment to requirements.txt
echo "# Test dependency change" >> requirements.txt
git add requirements.txt
git commit -m "Test: Requirements change for FULL_RESTART validation"
git push origin test-github-actions-deploy
```

**Expected Results**:
- ✅ Deployment type: `FULL_RESTART`
- ✅ Complete rebuild process
- ✅ All health checks pass

#### Test Case 3.3: Dockerfile Change
```bash
# Add comment to Dockerfile
echo "# Test dockerfile change - $(date)" >> Dockerfile
git add Dockerfile
git commit -m "Test: Dockerfile change for FULL_RESTART validation"
git push origin test-github-actions-deploy
```

**Expected Results**:
- ✅ Deployment type: `FULL_RESTART`
- ✅ Complete image rebuild
- ✅ System fully operational

### Phase 4: Manual Deployment Control

#### Test Case 4.1: Manual NO_RESTART
```bash
# Create any file change
echo "Manual test" >> src/utils.py
git add .
git commit -m "Test: Manual NO_RESTART override"
git push origin test-github-actions-deploy
```

**Manual Steps**:
1. Go to GitHub Actions → Intelligent VoxPersona Deployment
2. Click "Run workflow"
3. Select branch: `test-github-actions-deploy`
4. Set force_restart_type: `no-restart`
5. Run workflow

**Expected Results**:
- ✅ Deployment type: `NO_RESTART` (manual override)
- ✅ Files synced but no restart

#### Test Case 4.2: Manual FULL Restart
**Manual Steps**:
1. Run workflow with force_restart_type: `full`

**Expected Results**:
- ✅ Deployment type: `FULL_RESTART` (manual override)
- ✅ Complete system restart despite file type

### Phase 5: Error Handling & Rollback

#### Test Case 5.1: Simulate Deployment Failure
```bash
# Create intentional Docker error
echo "FROM nonexistent-image:latest" > Dockerfile.backup
cp Dockerfile Dockerfile.orig
cp Dockerfile.backup Dockerfile

git add Dockerfile
git commit -m "Test: Intentional deployment failure"
git push origin test-github-actions-deploy
```

**Expected Results**:
- ✅ Deployment fails during build
- ✅ Rollback mechanism activates
- ✅ Previous version restored
- ✅ System remains operational
- ✅ Failure logged to deployment.log

**Cleanup**:
```bash
# Restore original Dockerfile
cp Dockerfile.orig Dockerfile
git add Dockerfile
git commit -m "Test: Restore working Dockerfile"
git push origin test-github-actions-deploy
```

#### Test Case 5.2: Container Startup Failure
```bash
# Create configuration that causes startup failure
echo "INVALID_CONFIG=true" >> .env.template
git add .env.template
git commit -m "Test: Container startup failure scenario"
git push origin test-github-actions-deploy
```

**Expected Results**:
- ✅ Deployment detects container failure
- ✅ Health checks fail appropriately
- ✅ Rollback executes
- ✅ Previous version restored

## Performance Validation

### Benchmark Requirements

| Test Scenario | Target Duration | Acceptance Criteria |
|---------------|----------------|-------------------|
| NO_RESTART | < 15 seconds | ✅ Pass if < 15s |
| APP_ONLY | < 90 seconds | ✅ Pass if < 90s |  
| FULL_RESTART | < 180 seconds | ✅ Pass if < 180s |

### Performance Test Script

```bash
#!/bin/bash
# performance_test.sh

echo "🏃‍♂️ Performance Testing Script"

# Test NO_RESTART performance
echo "Testing NO_RESTART performance..."
start_time=$(date +%s)
echo "Performance test $(date)" >> README.md
git add README.md
git commit -m "Perf test: NO_RESTART timing"
git push origin test-github-actions-deploy

# Wait for completion and measure
# (Monitor in GitHub Actions interface)

# Test APP_ONLY performance  
echo "Testing APP_ONLY performance..."
echo "# Performance test $(date)" >> src/config.py
git add src/config.py
git commit -m "Perf test: APP_ONLY timing"
git push origin test-github-actions-deploy

# Test FULL_RESTART performance
echo "Testing FULL_RESTART performance..." 
echo "# Performance test $(date)" >> docker-compose.yml
git add docker-compose.yml
git commit -m "Perf test: FULL_RESTART timing"
git push origin test-github-actions-deploy
```

## Validation Checklist

### Pre-Production Validation
- [ ] All test scenarios execute successfully
- [ ] Performance benchmarks meet requirements
- [ ] Error handling works correctly
- [ ] Rollback mechanism functional
- [ ] Health checks comprehensive
- [ ] Logging and monitoring adequate
- [ ] Manual deployment controls work
- [ ] Security configuration verified

### Test Results Documentation

Create test results in this format:

```markdown
## Test Execution Results - [Date]

### NO_RESTART Tests
- ✅ Test 1.1: README Update - Duration: 8s
- ✅ Test 1.2: Multiple Docs - Duration: 12s

### APP_ONLY Tests  
- ✅ Test 2.1: Python Code - Duration: 45s
- ✅ Test 2.2: Prompts Update - Duration: 38s
- ✅ Test 2.3: Mixed Changes - Duration: 52s

### FULL_RESTART Tests
- ✅ Test 3.1: Docker Compose - Duration: 156s
- ✅ Test 3.2: Requirements - Duration: 142s
- ✅ Test 3.3: Dockerfile - Duration: 168s

### Manual Control Tests
- ✅ Test 4.1: Manual NO_RESTART - Duration: 7s
- ✅ Test 4.2: Manual FULL - Duration: 149s

### Error Handling Tests
- ✅ Test 5.1: Deployment Failure - Rollback: 23s
- ✅ Test 5.2: Startup Failure - Rollback: 31s

### Performance Summary
All tests meet performance requirements ✅
Ready for production deployment ✅
```

## Cleanup After Testing

```bash
# Remove test comments from files
git checkout HEAD~10 -- README.md DEPLOYMENT_GUIDE.md SETUP.md
git checkout HEAD~10 -- src/config.py src/bot.py src/utils.py
git checkout HEAD~10 -- docker-compose.yml Dockerfile requirements.txt

# Commit cleanup
git add .
git commit -m "Cleanup: Remove test changes"
git push origin test-github-actions-deploy

# Merge to main when ready
git checkout main
git merge test-github-actions-deploy
git push origin main
```

---

**Note**: Execute all tests systematically and document results before merging to main branch.