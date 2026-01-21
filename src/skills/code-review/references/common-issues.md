# Common Code Issues Quick Reference

## Security

### SQL Injection
```python
# ❌ Vulnerable
query = f"SELECT * FROM users WHERE id={user_id}"

# ✅ Safe
query = "SELECT * FROM users WHERE id=?"
cursor.execute(query, (user_id,))
```

### Hardcoded Secrets
```python
# ❌ Never do this
API_KEY = "sk-1234567890abcdef"

# ✅ Use environment variables
API_KEY = os.environ.get("API_KEY")
```

### XSS (Cross-Site Scripting)
```javascript
// ❌ Dangerous
element.innerHTML = userInput;

// ✅ Safe
element.textContent = userInput;
```

## Bugs

### Null/Undefined Access
```javascript
// ❌ Will crash if user is null
const name = user.name;

// ✅ Safe
const name = user?.name ?? "Unknown";
```

### Unhandled Exceptions
```python
# ❌ Will crash on error
data = json.loads(response)

# ✅ Handle errors
try:
    data = json.loads(response)
except json.JSONDecodeError as e:
    logger.error(f"Invalid JSON: {e}")
    return None
```

### Race Conditions
```python
# ❌ Race condition
if key in cache:
    value = cache[key]  # Key might be deleted here

# ✅ Atomic operation
value = cache.get(key)
if value is not None:
    # Use value
```

## Performance

### N+1 Query Problem
```python
# ❌ N+1 queries
for user in users:
    posts = db.query(f"SELECT * FROM posts WHERE user_id={user.id}")

# ✅ Single query with join
posts = db.query("SELECT * FROM posts WHERE user_id IN (?)", user_ids)
```

### Inefficient Algorithm
```python
# ❌ O(n²) - slow for large lists
for i in range(len(items)):
    for j in range(len(items)):
        if items[i] == items[j]:
            # ...

# ✅ O(n) - use set
seen = set()
for item in items:
    if item in seen:
        # ...
    seen.add(item)
```

### Memory Leak
```python
# ❌ File not closed on error
f = open("file.txt")
data = f.read()
f.close()

# ✅ Always closes
with open("file.txt") as f:
    data = f.read()
```

## Error Handling

### Silent Failures
```python
# ❌ Error swallowed
try:
    critical_operation()
except:
    pass

# ✅ Log and handle
try:
    critical_operation()
except Exception as e:
    logger.error(f"Operation failed: {e}")
    raise
```

### Missing Cleanup
```javascript
// ❌ Connection not closed on error
const conn = await db.connect();
const result = await conn.query(sql);
await conn.close();

// ✅ Always cleanup
const conn = await db.connect();
try {
    const result = await conn.query(sql);
    return result;
} finally {
    await conn.close();
}
```

## Type Safety

### Missing Type Checks
```python
# ❌ Assumes dict has key
value = config["key"]

# ✅ Check first
value = config.get("key")
if value is None:
    raise ValueError("Missing required config: key")
```

### Incorrect Types
```typescript
// ❌ Any defeats type safety
function process(data: any) {
    return data.value;
}

// ✅ Specific types
function process(data: { value: string }) {
    return data.value;
}
```
