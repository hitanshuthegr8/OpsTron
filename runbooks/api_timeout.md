# API Timeout Issues

## Issue Description
External API calls or internal service calls exceed configured timeout threshold, causing request failures.

## Symptoms
- 504 Gateway Timeout errors
- "Connection timeout after Xs" in logs
- Increased request latency
- Partial data returns

## Common Causes
1. Downstream service degradation
2. Network connectivity issues
3. Database query slowdowns
4. Thread pool exhaustion
5. Insufficient timeout configuration

## Detection Signals
- Log contains: "timeout", "connection reset", "read timeout"
- HTTP status code 504
- Requests taking > 30 seconds
- Circuit breaker trips

## Resolution Steps
1. Check downstream service health status
2. Review recent deployments to external dependencies
3. Analyze slow query logs if database-related
4. Verify network connectivity and DNS resolution
5. Check thread pool and connection pool metrics
6. Temporarily increase timeout if appropriate
7. Implement fallback or cache responses

## Prevention
- Set realistic timeout values (5-30s for most APIs)
- Implement circuit breakers and retry logic
- Add request timeouts at multiple layers
- Monitor p95/p99 latency metrics
- Use asynchronous processing for long operations
- Implement graceful degradation

## Monitoring Queries
- Track p50, p95, p99 response times
- Alert on timeout rate > 5%
- Monitor external API response times
