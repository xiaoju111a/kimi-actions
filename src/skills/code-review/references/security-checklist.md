# Security Review Checklist

## Input Validation
- [ ] All user input is validated
- [ ] Use whitelist instead of blacklist
- [ ] Validate data type, length, format
- [ ] Escape special characters

## Injection Prevention
- [ ] SQL uses parameterized queries
- [ ] Command execution avoids user input
- [ ] XSS output encoding
- [ ] LDAP/XML injection protection

## Authentication & Authorization
- [ ] Passwords use secure hashing (bcrypt/argon2)
- [ ] Sessions are securely generated and stored
- [ ] Sensitive operations require re-authentication
- [ ] Permission checks at every endpoint

## Sensitive Data
- [ ] Keys are not hardcoded
- [ ] Logs do not contain sensitive information
- [ ] Error messages do not leak system details
- [ ] Use HTTPS for transmission

## Encryption
- [ ] Use strong encryption algorithms (AES-256, RSA-2048+)
- [ ] Avoid MD5, SHA1, DES
- [ ] Secure random number generation
- [ ] Keys are securely stored

## Other
- [ ] CORS is properly configured
- [ ] CSRF protection
- [ ] Rate limiting
- [ ] Secure HTTP headers
