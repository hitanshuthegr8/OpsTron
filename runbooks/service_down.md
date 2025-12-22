# Service Unavailable / Crashed

## Issue Description
Service instance crashes, becomes unresponsive, or fails health checks.

## Symptoms
- 503 Service Unavailable errors
- Connection refused
- Health check failures
- No response from service endpoints

## Common Causes
1. Uncaught exceptions causing process crashes
2. Memory leaks leading to OOM errors
3. Resource exhaustion (CPU, memory, disk)
4. Configuration errors after deployment
5. Missing environment variables
6. Port conflicts

## Detection Signals
- Log contains: "NullPointerException", "OutOfMemoryError", "process exited"
- Container restarts
- Health endpoint returning 500/503
- No logs being generated

## Resolution Steps
1. Check container/process status and restart if needed
2. Review recent error logs before crash
3. Verify all environment variables are set
4. Check resource utilization (memory, CPU, disk)
5. Validate configuration files
6. Review recent code deployments for breaking changes
7. Check for port conflicts with other services

## Prevention
- Implement proper error handling and logging
- Add memory leak detection
- Configure resource limits appropriately
- Use health checks and readiness probes
- Implement graceful shutdown
- Add request rate limiting
- Monitor resource usage trends

## Quick Diagnostic Commands
```bash
# Check service status
systemctl status service-name

# View recent logs
journalctl -u service-name -n 100

# Check resource usage
top -p $(pgrep service-name)

# Test health endpoint
curl http://localhost:8000/health
```

## Recovery
- Restart service: `systemctl restart service-name`
- Scale up replicas if load-related
- Roll back recent deployment if introduced regression
