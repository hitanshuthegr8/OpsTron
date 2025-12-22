# Database Deadlock Resolution

## Issue Description
Database deadlock occurs when two or more transactions are waiting for each other to release locks, creating a circular dependency.

## Symptoms
- ERROR: Deadlock found when trying to get lock; try restarting transaction
- Query timeouts
- 500 errors on write operations
- Lock wait timeout exceeded messages

## Common Causes
1. Multiple transactions updating the same rows in different orders
2. Long-running transactions holding locks
3. Missing or inefficient database indexes
4. High concurrency on popular records

## Detection Signals
- Log contains: "deadlock", "lock wait timeout", "try restarting transaction"
- Multiple UPDATE/INSERT queries failing simultaneously
- Spike in transaction retry attempts

## Resolution Steps
1. Identify the conflicting transactions from database logs
2. Check `SHOW ENGINE INNODB STATUS` for deadlock details
3. Review recent code changes that modify transaction ordering
4. Add proper indexes on frequently locked columns
5. Implement retry logic with exponential backoff
6. Consider optimistic locking for high-contention resources

## Prevention
- Always access tables in the same order across transactions
- Keep transactions as short as possible
- Use row-level locking instead of table-level where appropriate
- Implement proper connection pooling

## Related Queries
- SELECT * FROM information_schema.innodb_locks;
- SHOW PROCESSLIST;
- SHOW ENGINE INNODB STATUS;
