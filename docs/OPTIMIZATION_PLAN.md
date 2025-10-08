# Zino's Chat 优化计划

## 📋 需求总览

### 原始需求
1. 语音生成模型效果生硬，需要更自然的 TTS
2. RAG 系统检索重复，缺乏多样性
3. 需要新增智能体实时查询并整合结果

---

## ✨ 优化后的需求表述

### 需求 1：自然语音合成系统升级

**问题描述**：
- 当前使用 gTTS 生成的语音缺乏情感表达和自然停顿
- 1.3 倍加速处理虽然提升活泼度，但无法解决根本问题
- 缺少对语调、重音、情感的精细控制

**目标**：
- 集成具备高自然度的 TTS 引擎，支持情感表达
- 保持当前的音频处理流程（Base64 编码 + HTML5 播放）
- 最小化代码改动，保证向后兼容
- 控制 API 调用成本，适合教育场景长期运行

**成功标准**：
- 语音自然度主观评分提升 60%+
- 集成改动代码行数 < 50 行
- 单次 TTS 调用延迟 < 2 秒
- 月度成本可控（目标 < $50 for 10K interactions）

---

### 需求 2：RAG 检索多样性与相关性增强

**问题描述**：
- 当前使用 MMR (Maximal Marginal Relevance) 算法，但参数 `lambda_mult=1` 导致完全优先相似度而非多样性
- `k=2, fetch_k=6` 检索量过小，且未使用重排序机制
- 缺少对话历史上下文，导致后续问题检索到相同文档
- 没有负面过滤机制，可能检索到不相关片段

**目标**：
- 实现混合检索策略（向量检索 + 关键词检索 + 重排序）
- 引入对话历史感知的上下文检索
- 添加检索结果去重和多样性控制
- 保持 ChromaDB 向量库不变，仅优化检索逻辑

**成功标准**：
- 连续 5 轮对话不出现完全相同的检索结果
- 检索相关性评分（人工标注）提升 40%+
- 检索延迟增加 < 500ms
- 代码改动集中在检索函数，不影响其他模块

---

### 需求 3：混合智能体 - 实时知识增强系统

**问题描述**：
- RAG 仅能检索预置的 PDF 知识库（db5/），无法获取实时信息
- 缺少针对特定问题的外部资源查询能力
- 用户问题超出知识库范围时，回答质量下降
- 没有自动判断何时需要外部查询的机制

**目标**：
- 新增智能路由层，判断问题是否需要外部查询
- 集成实时搜索工具（优先 Tavily API / DuckDuckGo）
- 实现 RAG 结果 + 搜索结果的智能融合
- 保留事实核查功能，标注信息来源（内部 vs 外部）

**成功标准**：
- 对超范围问题的回答准确率从 30% 提升到 75%+
- 智能路由决策准确率 > 85%
- 新增功能不影响现有 RAG 流程性能
- UI 中明确区分知识来源（知识库 vs 实时搜索）

---

## 🔧 技术方案

### 方案 1：TTS 系统升级

#### 方案对比

| 方案 | 自然度 | 集成难度 | 成本 | 推荐度 |
|------|--------|---------|------|--------|
| **OpenAI TTS** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | $15/1M字符 | ✅ 首选 |
| ElevenLabs | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | $22-99/月 | ⚠️ 高成本 |
| Azure Speech | ⭐⭐⭐⭐ | ⭐⭐⭐ | $16/1M字符 | 备选 |
| Coqui TTS (开源) | ⭐⭐⭐ | ⭐⭐ | 免费 | 技术复杂 |

#### 推荐方案：**OpenAI TTS**

**理由**：
- 已使用 OpenAI API，无需额外认证
- 支持 6 种预训练语音（推荐 `nova` - 女性、活泼）
- 原生支持流式输出和多种格式
- 与现有代码高度兼容

**实现要点**：
```python
from openai import OpenAI
client = OpenAI()

def speak_text_v2(text):
    response = client.audio.speech.create(
        model="tts-1",  # 或 tts-1-hd 获得更高质量
        voice="nova",   # Maria 的活泼语音
        input=text,
        speed=1.1       # 替代 pydub 加速
    )
    # 保持现有的 Base64 + HTML5 播放逻辑
```

---

### 方案 2：RAG 检索优化

#### 优化策略

**2.1 多样性参数调优**
```python
# 当前（问题所在）
vectordb.max_marginal_relevance_search(query, k=2, fetch_k=6, lambda_mult=1)
# lambda_mult=1 完全忽略多样性

# 优化方案
vectordb.max_marginal_relevance_search(
    query, 
    k=4,           # 增加检索量
    fetch_k=20,    # 扩大候选池
    lambda_mult=0.5  # 平衡相似度和多样性
)
```

**2.2 引入重排序机制**

使用 Cohere Rerank（或开源替代 FlashRank）：
```python
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import CohereRerank

compressor = CohereRerank(model="rerank-english-v3.0", top_n=3)
compression_retriever = ContextualCompressionRetriever(
    base_compressor=compressor,
    base_retriever=vectordb.as_retriever()
)
```

**2.3 对话历史过滤**
```python
def deduplicate_with_history(new_docs, chat_history):
    """基于对话历史去重"""
    used_doc_ids = set()
    for msg in chat_history:
        if 'retrieved_doc_ids' in msg:
            used_doc_ids.update(msg['retrieved_doc_ids'])
    
    return [doc for doc in new_docs if doc.metadata.get('id') not in used_doc_ids]
```

**2.4 混合检索（Hybrid Search）**

结合向量检索和关键词检索：
```python
from langchain.retrievers import EnsembleRetriever
from langchain.retrievers import BM25Retriever

# 向量检索器
vector_retriever = vectordb.as_retriever(search_kwargs={"k": 3})

# 关键词检索器
bm25_retriever = BM25Retriever.from_documents(all_docs)
bm25_retriever.k = 3

# 混合检索（0.6 向量 + 0.4 关键词）
ensemble_retriever = EnsembleRetriever(
    retrievers=[vector_retriever, bm25_retriever],
    weights=[0.6, 0.4]
)
```

#### 推荐方案组合：
1. **阶段一（快速改进）**：调整 MMR 参数 + 对话历史去重
2. **阶段二（深度优化）**：引入重排序 + 混合检索

---

### 方案 3：智能体实时查询系统

#### 架构设计

```
用户问题
    ↓
[智能路由器] ← LLM 判断：需要外部信息吗？
    ↓
    ├── Yes → [实时搜索工具] → [结果融合器] → 最终回答
    │              ↓
    │         [Tavily/DuckDuckGo]
    │
    └── No → [RAG 检索] → 传统流程
```

#### 工具选择

| 工具 | 优势 | 成本 | 推荐度 |
|------|------|------|--------|
| **Tavily API** | 专为 AI 设计，结构化输出 | $0.005/query | ✅ 首选 |
| DuckDuckGo | 完全免费，无限调用 | 免费 | 备选 |
| Google Custom Search | 高质量结果 | $5/1000 queries | 成本高 |

#### 实现方案：基于 LangChain Tools

```python
from langchain.agents import initialize_agent, Tool
from langchain_community.tools import TavilySearchResults

# 定义工具
search = TavilySearchResults(max_results=3)

tools = [
    Tool(
        name="knowledge_base",
        func=lambda q: vectordb.similarity_search(q, k=3),
        description="查询 Zino's Petrel 的专业知识库"
    ),
    Tool(
        name="web_search",
        func=search.run,
        description="搜索最新的保护动态、研究成果等实时信息"
    )
]

# 智能路由逻辑（简化版）
def enhanced_query(user_input):
    # 第一步：判断是否需要外部信息
    router_prompt = f"""
    问题：{user_input}
    
    判断这个问题是否需要实时信息？回答 'yes' 或 'no'
    需要实时信息的例子：最新研究、当前数量、近期事件
    不需要的例子：生物习性、栖息地描述、饮食习惯
    """
    
    need_search = llm(router_prompt).strip().lower() == 'yes'
    
    # 第二步：执行查询
    rag_results = vectordb.similarity_search(user_input, k=3)
    
    if need_search:
        search_results = search.run(user_input)
        # 融合结果
        combined_context = merge_sources(rag_results, search_results)
    else:
        combined_context = rag_results
    
    # 第三步：生成回答（添加来源标注）
    return generate_answer_with_sources(combined_context)
```

#### 结果融合策略

```python
def merge_sources(rag_docs, web_results):
    """智能融合 RAG 和搜索结果"""
    return {
        'internal_knowledge': rag_docs,  # 权威知识库
        'external_updates': web_results,  # 实时信息
        'merge_instruction': """
        优先使用 internal_knowledge 的权威信息，
        用 external_updates 补充最新动态，
        明确标注信息来源
        """
    }
```

---

## 📅 实施计划

### 阶段一：TTS 升级（预计 2-3 天）

**任务分解**：
- [ ] 1.1 获取 OpenAI TTS API 访问权限（已有 API key，直接可用）
- [ ] 1.2 编写新的 `speak_text_v2()` 函数
- [ ] 1.3 保留旧函数作为降级方案
- [ ] 1.4 A/B 测试对比语音质量
- [ ] 1.5 更新配置，切换到新 TTS
- [ ] 1.6 清理临时文件逻辑适配

**关键代码修改**：
- `main.py` 第 169-233 行（speak_text 函数）
- 新增 fallback 机制：OpenAI TTS 失败时回退到 gTTS

---

### 阶段二：RAG 检索优化（预计 4-5 天）

**任务分解**：
- [ ] 2.1 调整 MMR 参数（lambda_mult 改为 0.5）
- [ ] 2.2 实现对话历史去重机制
- [ ] 2.3 集成 Cohere Rerank API（或 FlashRank 开源版）
- [ ] 2.4 实现混合检索（向量 + BM25）
- [ ] 2.5 添加检索结果可视化（调试用）
- [ ] 2.6 性能测试和调优

**关键代码修改**：
- `main.py` 第 762-766 行（检索逻辑）
- 新增 `advanced_retrieval.py` 模块
- 修改 session_state 存储检索历史

**技术债务处理**：
- 当前 `most_relevant_texts` 只存储最后一次检索结果
- 改为列表存储所有历史，用于去重

---

### 阶段三：智能体集成（预计 5-7 天）

**任务分解**：
- [ ] 3.1 注册 Tavily API（免费额度 1000 次/月）
- [ ] 3.2 实现智能路由器（判断是否需要外部查询）
- [ ] 3.3 集成 Tavily 搜索工具
- [ ] 3.4 开发结果融合逻辑
- [ ] 3.5 UI 改造：添加来源标签（🔖 知识库 vs 🌐 实时搜索）
- [ ] 3.6 更新事实核查区域，展示多来源
- [ ] 3.7 端到端测试

**关键代码修改**：
- `main.py` 第 760-780 行（核心查询流程）
- 新增 `agent.py` 模块
- UI 修改：右侧事实核查区域（第 902-929 行）

**UI 设计草案**：
```html
<!-- 来源标签 -->
<div class="source-tags">
  🔖 知识库: Madeira 自然历史博物馆
  🌐 实时搜索: 2025年1月保护更新
</div>
```

---

### 阶段四：集成测试与优化（预计 3 天）

**任务分解**：
- [ ] 4.1 端到端功能测试
- [ ] 4.2 性能压测（100 并发对话）
- [ ] 4.3 成本分析和优化
- [ ] 4.4 用户体验测试（邀请 10 名测试用户）
- [ ] 4.5 Bug 修复和文档更新
- [ ] 4.6 部署到生产环境

**测试场景**：
1. 基础对话（纯 RAG）
2. 实时信息查询（智能体介入）
3. 重复问题（检索多样性验证）
4. 边缘情况（API 失败、超时等）

---

## 💰 成本估算

### API 调用成本

**OpenAI TTS**：
- 单次对话平均 50 字符
- 10,000 次对话 = 500,000 字符
- 成本：$15 × 0.5 = **$7.5/月**

**Tavily Search**：
- 假设 20% 对话需要外部查询
- 10,000 × 20% = 2,000 次
- 成本：$0.005 × 2,000 = **$10/月**

**Cohere Rerank**（可选）：
- 免费额度：1,000 次/月
- 超出后：$2/1,000 次
- 成本：**$0-20/月**

**总计**：约 **$20-40/月**（相比当前仅 OpenAI LLM 成本增加有限）

### 开发成本
- 预计总工时：14-18 天
- 可并行开发部分：TTS 和 RAG 优化

---

## 🎯 成功指标

### 量化指标

| 指标 | 当前 | 目标 | 测量方法 |
|------|------|------|---------|
| 语音自然度 | 2.5/5 | 4.0/5 | 用户主观评分 |
| 检索多样性 | 30% 重复 | < 5% 重复 | 连续对话分析 |
| 超范围问题准确率 | 30% | 75% | 测试集评估 |
| 平均响应时间 | 2.1s | < 3s | 系统日志 |
| 用户满意度 | 待测 | > 4.2/5 | 问卷调查 |

### 定性指标
- [ ] 语音听起来像"真人 Maria"而非机器人
- [ ] 用户感知到对话的"记忆"（不重复内容）
- [ ] 能回答"最新保护动态"等实时问题
- [ ] UI 清晰展示信息可信度

---

## ⚠️ 风险与缓解

### 风险 1：OpenAI TTS 延迟过高
- **缓解**：使用 `tts-1`（快速版）而非 `tts-1-hd`
- **降级方案**：保留 gTTS 作为备用

### 风险 2：重排序增加延迟
- **缓解**：仅在检索结果 > 5 个时启用
- **A/B 测试**：对比有无重排序的效果

### 风险 3：智能路由误判
- **缓解**：设置保守阈值，优先使用 RAG
- **人工审核**：前 500 次路由决策人工校验

### 风险 4：成本超预算
- **缓解**：设置 API 调用限额
- **监控**：实时追踪每日成本

---

## 📚 技术依赖更新

### 新增 Python 包

```txt
# requirements_new.txt（追加到现有 requirements.txt）

# TTS 升级
openai>=1.12.0  # 已有，确保版本支持 TTS

# RAG 优化
cohere>=4.37  # 重排序
rank-bm25>=0.2.2  # BM25 检索器
flashrank>=0.2.0  # 开源重排序（可选）

# 智能体工具
langchain-community>=0.2.10  # 已有
tavily-python>=0.3.0  # 搜索工具
duckduckgo-search>=4.0  # 备用搜索
```

### API 密钥配置

在 `.streamlit/secrets.toml` 中添加：
```toml
# 现有
OPENAI_API_KEY = "sk-..."

# 新增
COHERE_API_KEY = "..."  # https://dashboard.cohere.com/
TAVILY_API_KEY = "..."  # https://tavily.com/
```

---

## 🔄 回滚计划

每个阶段都保留原有代码作为备份：

```python
# 示例：TTS 回滚开关
USE_NEW_TTS = st.secrets.get("USE_NEW_TTS", True)

if USE_NEW_TTS:
    speak_text_v2(answer)  # OpenAI TTS
else:
    speak_text(answer)     # gTTS（旧版）
```

通过环境变量快速切换新旧系统，降低上线风险。

---

## 📖 参考资源

### 官方文档
- [OpenAI TTS API](https://platform.openai.com/docs/guides/text-to-speech)
- [LangChain Retrievers](https://python.langchain.com/docs/modules/data_connection/retrievers/)
- [Tavily Search](https://docs.tavily.com/)
- [Cohere Rerank](https://docs.cohere.com/reference/rerank)

### 技术文章
- [Advanced RAG Techniques](https://blog.langchain.dev/query-construction/)
- [Hybrid Search Best Practices](https://www.pinecone.io/learn/hybrid-search-intro/)
- [Building AI Agents with LangChain](https://python.langchain.com/docs/use_cases/agents/)

---

## ✅ 下一步行动

1. **立即执行**：
   - [ ] 获取 Tavily API 密钥（5 分钟）
   - [ ] 测试 OpenAI TTS 最小示例（30 分钟）
   - [ ] 调整 MMR 参数并验证效果（1 小时）

2. **本周完成**：
   - [ ] TTS 系统全面升级
   - [ ] RAG 多样性优化（阶段一）

3. **下周完成**：
   - [ ] 智能体原型开发
   - [ ] 端到端集成测试

---

**文档版本**：1.0  
**创建日期**：2025-10-06  
**负责人**：AI 开发团队  
**预计完成**：2025-10-20（14 工作日）


