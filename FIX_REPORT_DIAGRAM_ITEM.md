# DiagramItem 测试生成修复报告

## 问题
由于遗留代码库中严格的 C++ API 约束，`DiagramItem` 的自动化测试生成失败，LLM 默认情况下未能遵守这些约束。

### 问题详情
1.  **Mock 错误**: LLM 试图 Mock `DiagramPath` 并重写非虚方法，导致 vtable 错误。
2.  **构造函数不匹配**: `DiagramPath` 没有默认构造函数，并且需要特定的 `DiagramItem::TransformState` 枚举值（例如 `DiagramItem::TF_Cen`）。LLM 传递了 `0` 或幻觉产生的 `RectWhere` 等值。
3.  **引用约束**: `DiagramItem::setBrush(QColor &)` 接受一个 **非 const 引用**。LLM 传递了临时对象（例如 `item->setBrush(Qt::red)`），这在 C++ 中对于非 const 引用是非法的。

## 解决方案
我们更新了提示生成器 `src/qt_test_ai/llm_test_generator.py`，以强制执行针对这些类的特定编码规则。

### 应用的规则
1.  **禁止 Mock DiagramPath**: 明确禁止为该类创建 Mock。
2.  **严格的枚举使用**: 强制在 `DiagramPath` 构造函数中使用 `DiagramItem::TF_Cen`、`DiagramItem::TF_Top` 等。
3.  **左值强制**: 强制在传递给 `setBrush` 之前创建局部 `QColor` 变量。

## 结果
- **编译**: 成功。
- **测试通过**: 28/28。
- **失败**: 0。

## 验证日志
```
Totals: 28 passed, 0 failed, 0 skipped, 0 blacklisted, 9ms
********* Finished testing of TestDiagramItem *********
```
