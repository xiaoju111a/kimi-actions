# Python Best Practices

## 代码风格 (PEP8)
- 缩进使用 4 空格
- 行长度不超过 120 字符
- 类名使用 CamelCase
- 函数/变量使用 snake_case
- 常量使用 UPPER_CASE

## 类型提示
```python
def greet(name: str) -> str:
    return f"Hello, {name}"

def process(items: list[int]) -> dict[str, int]:
    return {"count": len(items)}
```

## 异常处理
```python
# ❌ 不要
try:
    do_something()
except:
    pass

# ✅ 正确
try:
    do_something()
except ValueError as e:
    logger.error(f"Invalid value: {e}")
    raise
```

## 资源管理
```python
# ✅ 使用 context manager
with open("file.txt") as f:
    content = f.read()

# ✅ 数据库连接
with db.connection() as conn:
    conn.execute(query)
```

## 常见问题
- 避免可变默认参数: `def foo(items=None)` 而非 `def foo(items=[])`
- 使用 f-string 而非 format()
- 列表推导式优于 map/filter
- 使用 `is None` 而非 `== None`
