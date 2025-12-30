# 代码覆盖率优化计划

## 当前现状（2025-12-25）

### 覆盖率指标
- **总体行覆盖率**: 2.6% (73 / 2848 行)
- **函数覆盖率**: 7.4% (13 / 176 函数)
- **分支覆盖率**: 0.7% (39 / 5789 分支)
- **已生成测试**: 3 个文件（225 行代码）

### 模块覆盖率明细
```
✅ 高覆盖（20%+）:
   - diagramtextitem.cpp: 39.1%
   - arrow.cpp: 19.3%

⚠️  低覆盖（<10%）:
   - diagramitem.cpp: 6.1%
   - diagramitemgroup.cpp: 8.9%

❌ 零覆盖（0%）:
   - mainwindow.cpp: 0% (1246 行)
   - diagramscene.cpp: 0% (377 行)
   - findreplacedialog.cpp: 0% (35 行)
   - deletecommand.cpp: 0% (12 行)
   - diagrampath.cpp: 0% (80 行)
```

---

## 优化目标

### 第一阶段（1-2周）：快速提升数据模型覆盖率
**目标**: 数据模型覆盖率从 6-9% → 40-50%

#### 1.1 增强 DiagramItem 测试（当前 6.1% → 目标 45%）

**待覆盖的关键函数**:
```
✗ setFont(QFont font)          - 0 次执行
✗ setScene(QGraphicsScene *s)  - 0 次执行
✗ isMoving() / setMoving(bool) - 0 次执行
✗ paint() 方法                 - 0 次执行
✗ mousePressEvent()            - 0 次执行
✗ mouseReleaseEvent()          - 0 次执行
✗ mouseMoveEvent()             - 0 次执行
```

**新增测试用例**:
- testDiagramItemFontProperty - 字体设置
- testDiagramItemMovingState - 移动状态管理
- testDiagramItemSceneIntegration - 场景集成
- testDiagramItemMouseInteraction - 鼠标事件（基础）
- testDiagramItemCoordinateSystem - 坐标系统
- testDiagramItemZValue - Z轴排序
- testDiagramItemSelection - 选择状态

**预期提升**: +350-400 行覆盖

#### 1.2 增强 DiagramPath 测试（当前 0% → 目标 50%）

**待覆盖内容**:
```
✗ 路径构造和初始化          - 完全未覆盖
✗ addPoint() 方法           - 完全未覆盖
✗ boundingRect() 计算        - 完全未覆盖
✗ paint() 渲染             - 完全未覆盖
✗ shape() 形状定义         - 完全未覆盖
```

**新增测试用例**:
- testDiagramPathConstruction - 构造函数
- testDiagramPathAddPoint - 添加点
- testDiagramPathBoundingRect - 边界计算
- testDiagramPathPaint - 绘制
- testDiagramPathWithMultiplePoints - 多点路径
- testDiagramPathEmpty - 空路径

**预期提升**: +80 行覆盖（全部）

#### 1.3 增强 DiagramItemGroup 测试（当前 8.9% → 目标 40%）

**新增测试用例**:
- testDiagramItemGroupAddItem - 添加项
- testDiagramItemGroupRemoveItem - 移除项
- testDiagramItemGroupBoundingRect - 聚合边界
- testDiagramItemGroupTransform - 变换操作
- testDiagramItemGroupPaint - 组绘制

**预期提升**: +120-150 行覆盖

---

### 第二阶段（2-4周）：覆盖命令和对话框
**目标**: 将 0% 的小模块提升到 30-50%

#### 2.1 DeleteCommand（当前 0% → 目标 40%）
```
testDeleteCommandConstruction
testDeleteCommandExecution
testDeleteCommandUndo
```
**预期**: 全部 12 行

#### 2.2 FindReplaceDialog（当前 0% → 目标 50%）
- 对话框初始化
- 查找功能
- 替换功能
- 状态管理

#### 2.3 Arrow（优化到 80%）
- 箭头类型
- 终点计算
- 边界条件

---

### 第三阶段（4-8周）：GUI 集成测试
**目标**: mainwindow.cpp 和 diagramscene.cpp 从 0% → 20%

#### 3.1 DiagramScene 事件处理（目标 20%）
- 鼠标事件处理
- 键盘事件处理
- 项目交互

#### 3.2 MainWindow 基础操作（目标 15%）
- 窗口初始化
- 菜单操作
- 工具栏操作

---

## 分阶段覆盖率预测

| 阶段 | 时间 | 目标覆盖率 | 优先模块 |
|------|------|-----------|---------|
| **当前** | - | 2.6% | - |
| **第一阶段完成** | 1-2周 | 15-18% | 数据模型 |
| **第二阶段完成** | 2-4周 | 22-25% | 命令+对话框 |
| **第三阶段完成** | 4-8周 | 35-40% | GUI集成 |
| **目标** | 8-12周 | **45-50%** | 全覆盖 |

---

## 改进的 LLM 提示词策略

### 关键优化点

1. **具体化测试目标**
   - ❌ 旧: "生成 DiagramItem 的测试"
   - ✅ 新: "生成 DiagramItem 的测试，覆盖以下未覆盖的函数：setFont, setScene, isMoving..."

2. **边界条件覆盖**
   - ✅ 空值测试
   - ✅ 负数测试
   - ✅ 边界值测试
   - ✅ 非法输入测试

3. **错误路径覆盖**
   - ✅ 测试错误条件
   - ✅ 测试异常情况
   - ✅ 测试无效状态

4. **集成场景**
   - ✅ 多对象交互
   - ✅ 状态转换
   - ✅ 事件链

---

## 实施细节

### 第一阶段：DiagramItem 扩展测试

**LLM 提示词**:
```
请为 Diagramscene 项目的 DiagramItem 类生成企业级单元测试。

已有覆盖（跳过）:
- 基础属性（brush, pen, size）
- 类型枚举
- 固定大小标记

未覆盖的关键方法（必须测试）:
1. void setFont(QFont) - 测试字体设置和获取
2. void setScene(QGraphicsScene *) - 测试场景关联
3. bool isMoving() / void setMoving(bool) - 测试移动状态机
4. void contextMenuEvent() - 测试右键菜单
5. QVariant itemChange() - 测试项目变更通知

生成的测试应该：
- 覆盖每个方法的多个代码路径
- 包含边界条件测试
- 测试与其他类的交互
- 验证状态转换的正确性

输出格式：QtTest 格式的 .cpp 文件，可直接编译到现有项目
```

### 实施时间表

**Week 1-2**:
- [ ] 生成 DiagramItem 扩展测试（+350行覆盖）
- [ ] 生成 DiagramPath 完整测试（+80行覆盖）
- [ ] 编译并验证所有新测试

**Week 3-4**:
- [ ] 生成 DiagramItemGroup 扩展测试
- [ ] 生成 DeleteCommand 完整测试
- [ ] 生成 Arrow 优化测试

**Week 5-8**:
- [ ] 生成 FindReplaceDialog 测试
- [ ] 开发 DiagramScene 基础事件测试
- [ ] 开发 MainWindow 集成测试框架

---

## 技术实现路线

### 工具链优化
1. **覆盖率分析** → 生成"未覆盖函数"列表
2. **智能提示生成** → 针对每个未覆盖函数
3. **LLM 测试生成** → 提高针对性
4. **自动编译测试** → 验证有效性
5. **覆盖率验证** → 确认提升

### 脚本支持
```powershell
# 生成覆盖率分析报告
.\tools\analyze_coverage_gaps.ps1

# 生成 LLM 提示词
.\tools\generate_llm_prompts.ps1 -CoverageFile coverage_report.html

# 运行新生成的测试
.\tools\run_new_tests.ps1

# 生成对比报告
.\tools\compare_coverage.ps1 -Before baseline_coverage.json -After current_coverage.json
```

---

## 成功指标

### 第一阶段验收标准
- [ ] DiagramItem: 6.1% → 45%+
- [ ] DiagramPath: 0% → 50%+
- [ ] DiagramItemGroup: 8.9% → 40%+
- [ ] **总体**: 2.6% → 15%+
- [ ] 所有新测试通过编译
- [ ] 没有引入新的编译警告

### 最终目标（第三阶段）
- [ ] **总体覆盖率**: 45-50%
- [ ] **关键模块**: 70-80%
- [ ] **维护成本**: <2 小时/周
- [ ] **CI/CD 集成**: 完全自动化

---

## 相关资源

- 覆盖率报告: `reports/coverage_report.html`
- 测试框架文档: `TESTING_SUMMARY.md`
- LLM 集成代码: `tools/analyze_and_generate.py`

**更新日期**: 2025-12-25
