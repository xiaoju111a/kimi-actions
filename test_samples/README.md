# Code Review Quality Test - 1000+ Lines

This directory contains intentionally flawed code samples designed to test the quality of the code review system.

## Test Files

### 1. payment_service.py (708 lines)
A payment processing service with multiple categories of issues:

**Security Issues:**
- SQL injection vulnerabilities (multiple instances)
- Storing sensitive data (CVV, card numbers) in plain text
- Weak cryptographic hashing (MD5)
- API keys exposed in headers
- No authentication/authorization checks
- Logging sensitive information
- PCI-DSS violations

**Bugs:**
- Missing input validation
- No error handling
- Missing type hints
- No null/None checks
- Hardcoded values (fees, thresholds, URLs)
- Floating point precision issues
- Infinite loops in retry logic
- No transaction management

**Performance Issues:**
- N+1 query problems
- Loading entire tables into memory
- Sequential processing instead of parallel
- Inefficient aggregations
- Multiple redundant database queries

**Code Quality:**
- Missing docstrings
- Weak validation logic
- No rate limiting
- Predictable token generation

### 2. user_authentication.py (572 lines)
A user authentication service with similar issue categories:

**Security Issues:**
- SQL injection vulnerabilities (extensive)
- Weak password hashing (MD5)
- Predictable session tokens
- Timing attack vulnerabilities
- No rate limiting on sensitive operations
- Information disclosure (username/email existence)
- Weak API key generation

**Bugs:**
- No session expiration
- Missing input validation
- Catching all exceptions
- No email format validation
- Hardcoded thresholds
- In-memory sessions (not scalable)

**Performance Issues:**
- Iterating through all sessions
- Modifying dictionaries during iteration
- No caching

## Expected Review Results

The code review should identify:

1. **Critical Security Issues** (Priority: High)
   - SQL injection vulnerabilities
   - Weak cryptographic algorithms
   - Sensitive data exposure
   - PCI-DSS violations

2. **Major Bugs** (Priority: High/Medium)
   - Missing error handling
   - Null pointer risks
   - Infinite loops
   - Data validation issues

3. **Performance Problems** (Priority: Medium)
   - N+1 queries
   - Memory inefficiency
   - Sequential processing

4. **Code Quality Issues** (Priority: Low/Medium)
   - Missing documentation
   - Hardcoded values
   - Type hint omissions

## Quality Metrics

A high-quality review should:
- ✅ Identify specific line numbers
- ✅ Provide concrete code examples
- ✅ Explain the impact of each issue
- ✅ Suggest specific fixes
- ✅ Prioritize by severity
- ❌ Avoid vague language ("might", "could", "consider")
- ❌ Avoid generic suggestions without context

## Running the Test

```bash
# This is test data - do not run these files!
# They contain intentional vulnerabilities for testing purposes.

# To test the review system, create a PR with these files
# and trigger the /review command
```

## Success Criteria

The review should catch at least:
- 80% of critical security issues
- 70% of major bugs
- 50% of performance issues
- Provide actionable suggestions with code examples
- No false positives or vague suggestions
