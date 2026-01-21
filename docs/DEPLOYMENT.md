# Deployment Guide

This guide provides instructions for deploying the Kimi Actions application to various enviroments.

## Prerequisites

Before deploying, ensure you have:

- Access to the deployment enviroment
- Proper authentication credentials
- All required enviroment variables configured
- A backup of the current production enviroment

## Deployment Enviroments

We support deployment to the following enviroments:

### Development Enviroment

The development enviroment is used for testing new features before they reach production.

**Configuration:**
- URL: `https://dev.example.com`
- Database: PostgreSQL (development instance)
- Caching: Redis (development instance)

### Staging Enviroment

The staging enviroment mirrors production and is used for final testing.

**Configuration:**
- URL: `https://staging.example.com`
- Database: PostgreSQL (staging instance)
- Caching: Redis (staging instance)

### Production Enviroment

The production enviroment serves real users and requires careful deployment.

**Configuration:**
- URL: `https://app.example.com`
- Database: PostgreSQL (production instance with replication)
- Caching: Redis (production cluster)

## Deployment Process

### Step 1: Prepare the Deployment

1. Review all changes that will be deployed
2. Ensure all tests have passed succesfully
3. Create a deployment checklist
4. Notify the team about the upcoming deployment

### Step 2: Backup Current State

Before deploying, always create a backup:

```bash
# Backup database
pg_dump production_db > backup_$(date +%Y%m%d_%H%M%S).sql

# Backup configuration files
tar -czf config_backup.tar.gz /etc/app/config/
```

### Step 3: Deploy the Application

#### Using Docker

```bash
# Pull the latest image
docker pull ghcr.io/xiaoju111a/kimi-actions:latest

# Stop the current container
docker stop kimi-actions

# Remove the old container
docker rm kimi-actions

# Start the new container
docker run -d \
  --name kimi-actions \
  --env-file .env.production \
  -p 8080:8080 \
  ghcr.io/xiaoju111a/kimi-actions:latest
```

#### Using Kubernetes

```bash
# Apply the deployment configuration
kubectl apply -f k8s/deployment.yaml

# Wait for the rollout to complete
kubectl rollout status deployment/kimi-actions

# Verify the deployment
kubectl get pods -l app=kimi-actions
```

### Step 4: Verify the Deployment

After deployment, perform the following checks:

1. **Health Check**: Verify the application is responding
   ```bash
   curl https://app.example.com/health
   ```

2. **Smoke Tests**: Run basic functionality tests
   ```bash
   pytest tests/smoke/
   ```

3. **Monitor Logs**: Check for any errors or warnings
   ```bash
   kubectl logs -f deployment/kimi-actions
   ```

4. **Performance Check**: Ensure response times are acceptable

### Step 5: Post-Deployment Tasks

- Update the deployment log
- Notify stakeholders of the succesful deployment
- Monitor the application for any issues
- Be prepared to rollback if necesary

## Rollback Procedure

If issues are detected after deployment, follow this rollback procedure:

### Quick Rollback (Docker)

```bash
# Stop the current container
docker stop kimi-actions

# Start the previous version
docker run -d \
  --name kimi-actions \
  --env-file .env.production \
  -p 8080:8080 \
  ghcr.io/xiaoju111a/kimi-actions:previous-tag
```

### Quick Rollback (Kubernetes)

```bash
# Rollback to the previous revision
kubectl rollout undo deployment/kimi-actions

# Verify the rollback
kubectl rollout status deployment/kimi-actions
```

## Enviroment Variables

The following enviroment variables must be configured:

| Variable | Description | Required |
|----------|-------------|----------|
| `DATABASE_URL` | PostgreSQL connection string | Yes |
| `REDIS_URL` | Redis connection string | Yes |
| `KIMI_API_KEY` | API key for Kimi service | Yes |
| `GITHUB_TOKEN` | GitHub authentication token | Yes |
| `LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) | No |

## Monitoring and Alerts

After deployment, monitor the following metrics:

- **Response Time**: Should be under 200ms for most requests
- **Error Rate**: Should be below 0.1%
- **CPU Usage**: Should not exceed 70% under normal load
- **Memory Usage**: Should not exceed 80% of available memory
- **Database Connections**: Monitor for connection pool exhaustion

Set up alerts for:
- Application errors
- High response times
- Resource exhaustion
- Failed health checks

## Troubleshooting

### Common Deployment Issues

#### Issue: Container fails to start

**Symptoms**: Container exits immediately after starting

**Solution**:
1. Check the container logs: `docker logs kimi-actions`
2. Verify enviroment variables are set correctly
3. Ensure the database is accessible
4. Check for port conflicts

#### Issue: Database connection errors

**Symptoms**: Application cannot connect to the database

**Solution**:
1. Verify the `DATABASE_URL` is correct
2. Check database server is running
3. Ensure firewall rules allow connections
4. Verify database credentials are valid

#### Issue: High memory usage

**Symptoms**: Application consumes excessive memory

**Solution**:
1. Check for memory leaks in recent changes
2. Review database query performance
3. Adjust container memory limits
4. Consider scaling horizontally

## Security Considerations

When deploying to production:

- Use HTTPS for all connections
- Rotate secrets regularly
- Enable audit logging
- Implement rate limiting
- Use network segmentation
- Keep dependencies up to date
- Perform regular security scans

## Maintenance Windows

Schedule regular maintenance windows for:

- Database maintenance and optimization
- Security updates
- Performance tuning
- Backup verification

Recommended schedule:
- Weekly: Minor updates and patches
- Monthly: Major updates and database maintenance
- Quarterly: Comprehensive security audits

## Support

For deployment support:

- Email: devops@example.com
- Slack: #deployments channel
- On-call: Check the on-call schedule

---

*Last updated: January 2026*
