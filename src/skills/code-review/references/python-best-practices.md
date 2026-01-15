# Python Best Practices

## Code Style (PEP8)
- Use 4 spaces for indentation
- Line length should not exceed 120 characters
- Class names use CamelCase
- Functions/variables use snake_case
- Constants use UPPER_CASE

## Type Hints
```python
def greet(name: str) -> str:
    return f"Hello, {name}"

def process(items: list[int]) -> dict[str, int]:
    return {"count": len(items)}
```

## Exception Handling
```python
# ❌ Don't
try:
    do_something()
except:
    pass

# ✅ Correct
try:
    do_something()
except ValueError as e:
    logger.error(f"Invalid value: {e}")
    raise
```

## Resource Management
```python
# ✅ Use context manager
with open("file.txt") as f:
    content = f.read()

# ✅ Database connection
with db.connection() as conn:
    conn.execute(query)
```

## Common Issues
- Avoid mutable default arguments: `def foo(items=None)` instead of `def foo(items=[])`
- Use f-strings instead of format()
- List comprehensions are preferred over map/filter
- Use `is None` instead of `== None`
