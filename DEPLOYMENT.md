# SimulatorTools Production Deployment Checklist

## Pre-Deployment

- [ ] Update version tags in docker-compose.yml
- [ ] Review and merge all feature branches to main
- [ ] Run all tests locally: `pytest backend/tests`
- [ ] Build and tag Docker images:
  ```bash
  docker build -t ghcr.io/rdwr-rotemw/simtools-backend:latest -f backend/Dockerfile .
  docker build -t ghcr.io/rdwr-rotemw/simtools-frontend:latest -f frontend/Dockerfile .
  ```
- [ ] Push images to registry:
  ```bash
  docker push ghcr.io/rdwr-rotemw/simtools-backend:latest
  docker push ghcr.io/rdwr-rotemw/simtools-frontend:latest
  ```

## Initial Production Setup (New Environment)

### 1. Deploy Docker Stack

```bash
# On production server
cd /opt/SimTools
docker-compose up -d
```

### 2. Wait for Health Checks

```bash
# All containers should show (healthy)
docker ps
```

### 3. Run Database Migrations

```bash
# Run Alembic migrations
docker exec simtools-backend alembic upgrade head
```

### 4. Initialize Production Database

```bash
# Run initialization script
docker exec simtools-backend python -m backend.scripts.init_production
```

**Expected output:**
```
============================================================
SimulatorTools Production Initialization
============================================================

1. Checking admin user...
   ✅ Admin workspace is correct ('*')

2. Checking for NULL workspaces...
   ✅ No NULL workspaces found

3. Verifying all users...
   Total users: 3
   --------------------------------------------------
     1 | admin                | *
     2 | auto                 | default
     3 | cc_scale             | cc_scale
   --------------------------------------------------

4. Workspace distribution:
   default             : 1 user(s)
   cc_scale            : 1 user(s)
   *                   : 1 user(s)

============================================================
✅ Production initialization complete!
============================================================
```

### 5. Verify Critical Configuration

```bash
# Check database users
docker exec simtools-postgres psql -U simtools_user -d simulators -c "SELECT user_id, username, workspace FROM users;"

# Check backend logs
docker logs simtools-backend --tail 50

# Check frontend is accessible
curl -k https://localhost:8443
```

## Update Existing Production

### 1. Pull Latest Images

```bash
cd /opt/SimTools
docker-compose pull
```

### 2. Stop Services

```bash
docker-compose down
```

### 3. Backup Database (CRITICAL!)

```bash
# Backup PostgreSQL
docker exec simtools-postgres pg_dump -U simtools_user simulators > backup_$(date +%Y%m%d_%H%M%S).sql

# Backup MongoDB
docker exec simtools-mongodb mongodump --out /tmp/mongo_backup
docker cp simtools-mongodb:/tmp/mongo_backup ./mongo_backup_$(date +%Y%m%d_%H%M%S)
```

### 4. Start Services

```bash
docker-compose up -d
```

### 5. Run Migrations

```bash
docker exec simtools-backend alembic upgrade head
```

### 6. Re-run Initialization Script

```bash
docker exec simtools-backend python -m backend.scripts.init_production
```

### 7. Smoke Test

- [ ] Log in as admin user
- [ ] Verify workspace shows as '*'
- [ ] Create a test user with specific workspace
- [ ] Log in as test user
- [ ] Verify workspace filtering works
- [ ] Create a test device
- [ ] Delete test device and user

## Post-Deployment Verification

Run this command to verify workspace data integrity:

```bash
docker exec simtools-postgres psql -U simtools_user -d simulators -c "
SELECT
    COUNT(*) as total_users,
    COUNT(CASE WHEN workspace IS NULL THEN 1 END) as null_workspaces,
    COUNT(CASE WHEN workspace = '*' THEN 1 END) as admin_users,
    COUNT(CASE WHEN workspace = 'default' THEN 1 END) as default_users
FROM users;
"
```

**Expected:** null_workspaces should be **0**

## Rollback Procedure

If deployment fails:

```bash
# Stop current containers
docker-compose down

# Restore database backup
cat backup_YYYYMMDD_HHMMSS.sql | docker exec -i simtools-postgres psql -U simtools_user -d simulators

# Revert to previous image version
# Edit docker-compose.yml to use previous tag
docker-compose up -d
```

## Troubleshooting

### Issue: Users have NULL workspace

**Fix:**
```bash
docker exec simtools-backend python -m backend.scripts.init_production
```

### Issue: "Map not found in workspace 'default'" error

**Root Cause:** User has NULL or incorrect workspace

**Fix:**
```bash
# Check user workspace
docker exec simtools-postgres psql -U simtools_user -d simulators -c "SELECT user_id, username, workspace FROM users WHERE username = 'YOUR_USERNAME';"

# Update if NULL
docker exec simtools-postgres psql -U simtools_user -d simulators -c "UPDATE users SET workspace = 'CORRECT_WORKSPACE' WHERE username = 'YOUR_USERNAME';"

# User must log out and log back in for changes to take effect
```

### Issue: Admin can't see all workspaces

**Fix:**
```bash
docker exec simtools-postgres psql -U simtools_user -d simulators -c "UPDATE users SET workspace = '*' WHERE username = 'admin';"
```

## Emergency Contacts

- Backend issues: Check `docker logs simtools-backend`
- Database issues: Check `docker logs simtools-postgres`
- Frontend issues: Check `docker logs simtools-frontend`

## Monitoring

After deployment, monitor for 30 minutes:

```bash
# Watch backend logs
docker logs -f simtools-backend

# Check for errors
docker logs simtools-backend 2>&1 | grep -i error

# Monitor resource usage
docker stats
```
