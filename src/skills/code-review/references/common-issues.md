# Common Code Issues Reference

This document provides detailed examples of common code issues across different programming languages.

## Python Common Issues

### 1. Comparison with None
```python
# ❌ Bad: Using == or !=
if value == None:
    pass
if value != None:
    pass

# ✅ Good: Using is or is not
if value is None:
    pass
if value is not None:
    pass
```

**Why**: `is` checks identity, `==` checks equality. `None` is a singleton, so `is` is more efficient and semantically correct.

### 2. Bare Except Clauses
```python
# ❌ Bad: Catches everything including KeyboardInterrupt
try:
    risky_operation()
except:
    pass

# ✅ Good: Catch specific exceptions
try:
    risky_operation()
except ValueError as e:
    logger.error(f"Invalid value: {e}")
    raise
except IOError as e:
    logger.error(f"IO error: {e}")
    return None
```

### 3. Mutable Default Arguments
```python
# ❌ Bad: List is shared across all calls
def add_item(item, items=[]):
    items.append(item)
    return items

# ✅ Good: Use None and create new list
def add_item(item, items=None):
    if items is None:
        items = []
    items.append(item)
    return items
```

### 4. String Concatenation in Loops
```python
# ❌ Bad: O(n²) complexity
result = ""
for item in items:
    result += str(item)

# ✅ Good: O(n) complexity
result = "".join(str(item) for item in items)
```

### 5. Not Closing Resources
```python
# ❌ Bad: File might not be closed on exception
f = open("file.txt")
data = f.read()
f.close()

# ✅ Good: Use context manager
with open("file.txt") as f:
    data = f.read()
```

## JavaScript/TypeScript Common Issues

### 1. Loose Equality
```javascript
// ❌ Bad: Type coercion can cause bugs
if (value == null) { }
if (count == 0) { }

// ✅ Good: Strict equality
if (value === null || value === undefined) { }
if (count === 0) { }
```

### 2. Missing Await
```javascript
// ❌ Bad: Promise not awaited
async function processData() {
    fetchData();  // Returns unhandled promise
    return result;
}

// ✅ Good: Await the promise
async function processData() {
    const data = await fetchData();
    return processResult(data);
}
```

### 3. Callback Hell
```javascript
// ❌ Bad: Nested callbacks
getData(function(a) {
    getMoreData(a, function(b) {
        getMoreData(b, function(c) {
            console.log(c);
        });
    });
});

// ✅ Good: Use async/await
async function processData() {
    const a = await getData();
    const b = await getMoreData(a);
    const c = await getMoreData(b);
    console.log(c);
}
```

### 4. Not Handling Promise Rejections
```javascript
// ❌ Bad: Unhandled rejection
fetch('/api/data')
    .then(response => response.json())
    .then(data => console.log(data));

// ✅ Good: Handle errors
fetch('/api/data')
    .then(response => response.json())
    .then(data => console.log(data))
    .catch(error => console.error('Failed:', error));

// ✅ Better: Use async/await with try-catch
async function fetchData() {
    try {
        const response = await fetch('/api/data');
        const data = await response.json();
        console.log(data);
    } catch (error) {
        console.error('Failed:', error);
    }
}
```

### 5. Modifying Array During Iteration
```javascript
// ❌ Bad: Skips elements
const arr = [1, 2, 3, 4];
for (let i = 0; i < arr.length; i++) {
    if (arr[i] % 2 === 0) {
        arr.splice(i, 1);  // Modifies array being iterated
    }
}

// ✅ Good: Filter to new array
const arr = [1, 2, 3, 4];
const filtered = arr.filter(x => x % 2 !== 0);
```

## Go Common Issues

### 1. Ignoring Errors
```go
// ❌ Bad: Error ignored
data, _ := readFile("config.json")
processData(data)

// ✅ Good: Handle error
data, err := readFile("config.json")
if err != nil {
    return fmt.Errorf("failed to read config: %w", err)
}
processData(data)
```

### 2. Not Closing Resources
```go
// ❌ Bad: File might not be closed
file, err := os.Open("data.txt")
if err != nil {
    return err
}
data, err := io.ReadAll(file)
file.Close()

// ✅ Good: Use defer
file, err := os.Open("data.txt")
if err != nil {
    return err
}
defer file.Close()
data, err := io.ReadAll(file)
```

### 3. Goroutine Leaks
```go
// ❌ Bad: Goroutine never exits
func process() {
    ch := make(chan int)
    go func() {
        for {
            select {
            case v := <-ch:
                handle(v)
            }
        }
    }()
}

// ✅ Good: Use context for cancellation
func process(ctx context.Context) {
    ch := make(chan int)
    go func() {
        for {
            select {
            case v := <-ch:
                handle(v)
            case <-ctx.Done():
                return
            }
        }
    }()
}
```

### 4. Race Conditions
```go
// ❌ Bad: Concurrent map access
var cache = make(map[string]string)

func get(key string) string {
    return cache[key]  // Race condition
}

func set(key, value string) {
    cache[key] = value  // Race condition
}

// ✅ Good: Use mutex
var (
    cache = make(map[string]string)
    mu    sync.RWMutex
)

func get(key string) string {
    mu.RLock()
    defer mu.RUnlock()
    return cache[key]
}

func set(key, value string) {
    mu.Lock()
    defer mu.Unlock()
    cache[key] = value
}
```

## Java Common Issues

### 1. Empty Catch Blocks
```java
// ❌ Bad: Silently swallows exceptions
try {
    riskyOperation();
} catch (Exception e) {
    // Empty catch
}

// ✅ Good: Log and handle
try {
    riskyOperation();
} catch (Exception e) {
    logger.error("Operation failed", e);
    throw new RuntimeException("Failed to process", e);
}
```

### 2. String Comparison with ==
```java
// ❌ Bad: Compares references
if (str1 == str2) {
    // ...
}

// ✅ Good: Compare values
if (str1.equals(str2)) {
    // ...
}

// ✅ Better: Handle null
if (Objects.equals(str1, str2)) {
    // ...
}
```

### 3. Not Closing Resources
```java
// ❌ Bad: Resource might not be closed
FileInputStream fis = new FileInputStream("file.txt");
int data = fis.read();
fis.close();

// ✅ Good: Use try-with-resources
try (FileInputStream fis = new FileInputStream("file.txt")) {
    int data = fis.read();
}
```

### 4. Inefficient String Concatenation
```java
// ❌ Bad: Creates many String objects
String result = "";
for (int i = 0; i < 1000; i++) {
    result += i;
}

// ✅ Good: Use StringBuilder
StringBuilder sb = new StringBuilder();
for (int i = 0; i < 1000; i++) {
    sb.append(i);
}
String result = sb.toString();
```

## SQL Common Issues

### 1. SQL Injection
```python
# ❌ Bad: String concatenation
query = f"SELECT * FROM users WHERE username='{username}'"
cursor.execute(query)

# ✅ Good: Parameterized query
query = "SELECT * FROM users WHERE username=?"
cursor.execute(query, (username,))
```

### 2. N+1 Query Problem
```python
# ❌ Bad: One query per user
users = User.objects.all()
for user in users:
    orders = Order.objects.filter(user=user)  # N queries

# ✅ Good: Prefetch related data
users = User.objects.prefetch_related('orders').all()
for user in users:
    orders = user.orders.all()  # No additional queries
```

### 3. Missing Indexes
```sql
-- ❌ Bad: No index on frequently queried column
SELECT * FROM orders WHERE user_id = 123;  -- Full table scan

-- ✅ Good: Add index
CREATE INDEX idx_orders_user_id ON orders(user_id);
SELECT * FROM orders WHERE user_id = 123;  -- Index scan
```

## Security Common Issues

### 1. Hardcoded Secrets
```python
# ❌ Bad: Hardcoded credentials
API_KEY = "sk-1234567890abcdef"
DATABASE_URL = "postgresql://user:password@localhost/db"

# ✅ Good: Use environment variables
import os
API_KEY = os.environ.get("API_KEY")
DATABASE_URL = os.environ.get("DATABASE_URL")
```

### 2. XSS Vulnerability
```javascript
// ❌ Bad: Directly inserting user input
element.innerHTML = userInput;

// ✅ Good: Escape or use textContent
element.textContent = userInput;
// Or use a sanitization library
element.innerHTML = DOMPurify.sanitize(userInput);
```

### 3. Path Traversal
```python
# ❌ Bad: User input in file path
filename = request.GET['file']
with open(f"/uploads/{filename}") as f:
    return f.read()

# ✅ Good: Validate and sanitize
import os
filename = os.path.basename(request.GET['file'])  # Remove path components
safe_path = os.path.join("/uploads", filename)
if not safe_path.startswith("/uploads/"):
    raise ValueError("Invalid file path")
with open(safe_path) as f:
    return f.read()
```

### 4. Weak Cryptography
```python
# ❌ Bad: MD5 for passwords
import hashlib
password_hash = hashlib.md5(password.encode()).hexdigest()

# ✅ Good: Use bcrypt or argon2
import bcrypt
password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
```

## Performance Common Issues

### 1. Inefficient Loops
```python
# ❌ Bad: O(n²) complexity
result = []
for item in items:
    if item not in result:  # O(n) lookup
        result.append(item)

# ✅ Good: O(n) complexity
result = list(set(items))  # O(1) lookup in set
```

### 2. Loading All Data at Once
```python
# ❌ Bad: Loads entire table into memory
users = User.objects.all()
for user in users:
    process(user)

# ✅ Good: Use iterator/chunking
for user in User.objects.iterator(chunk_size=1000):
    process(user)
```

### 3. Blocking I/O in Async Code
```python
# ❌ Bad: Blocking call in async function
async def fetch_data():
    response = requests.get(url)  # Blocks event loop
    return response.json()

# ✅ Good: Use async HTTP client
async def fetch_data():
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()
```

## When to Flag These Issues

- **Always flag**: Security issues, SQL injection, XSS, hardcoded secrets
- **Flag if clear**: Performance issues with obvious impact (N+1 queries, O(n²) loops)
- **Flag if obvious**: Language-specific anti-patterns (== None, bare except)
- **Don't flag**: Minor style issues, pre-existing code, subjective preferences
