"""
Fact-Check 工具 - 智能摘要和验证
结合知识库检索和可选的网络搜索，生成总结性文本
"""

import os
from langchain_community.llms import Tongyi
from dotenv import load_dotenv

load_dotenv()

def get_friendly_filename(source_file):
    """
    Convert technical source file names to user-friendly names
    """
    filename_mapping = {
        # Your Excel mappings
        '41_S_1-43.pdf': 'Simons et al 2013 - Diablotin Pterodroma hasitata Biography of the Black-capped Petrel',
        '2024FloodZinos1stBritain.pdf': 'Flood 2024 - Zino\'s Petrel off Scilly new to Britain',
        '3906_pterodroma_madeira.pdf': 'BirdLife International 2021 - Pterodroma madeira Zinos Petrel',
        'Conservation_of_Zinos_petrel_Pterodroma.pdf': 'Zino et al 2001 - Conservation of Zinos petrel Pterodroma madeira in Madeira',
        'conservation-of-zinos-petrel-pterodroma-madeira-in-the-archipelago-of-madeira.pdf': 'Zino et al 2001 - Conservation of Zinos petrel Pterodroma madeira in Madeira',
        'Madeira_Zinos_Petrel_2010_0.pdf': 'BirdLife International 2010 - Race against the clock to save Zinos Petrel',
        'Madeira-2021.pdf': 'Flood 2021 - ORIOLE BIRDING TOUR TO MADEIRA ENDEMICS AND SEABIRDS 5-9 JULY 2021',
        'madeira-2024-text.pdf': 'Koppenol 2024 - MADEIRA TOUR REPORT 2024',
        'Madeira2004_NB.pdf': 'Brinkley 2004 - Zinos Petrel at sea off Madeira 27 April 2004',
        'pterodromaRefs_v1.15.pdf': 'Hobbs 2017 - Pterodroma Reference List - Comprehensive bibliography of gadfly petrels',
        'Shirihai_Jamaica_AtSea_Nov09.pdf': 'Shirihai et al 2010 - Jamaica Petrel Pterodroma caribbaea Pelagic expedition report',
        'srep23447.pdf': 'Ramos et al 2016 - Global spatial ecology of three closely related gadfly petrels',
        'The_separation_of_Pterodroma_madeira_Zin.pdf': 'Zino et al 2008 - The separation of Pterodroma madeira from Pterodroma feae',
        'v36n6p586.pdf': 'Patteson & Brinkley 2004 - A Petrel Primer - The Gadflies of North Carolina',
        'v40n6p28.pdf': 'Hess 2008 - Feas or Zinos Petrel',
        'Zino_s_Petrel_Pterodroma_madeira_off_Nor.pdf': 'Patteson et al 2013 - Zinos Petrel Pterodroma madeira off North Carolina - First for North America',
        'zinos-petrel-1995.pdf': 'Zino et al 1995 - Action Plan for Zinos Petrel Pterodroma madeira',
        'zlae123.pdf': 'Rando et al 2024 - Pterodroma zinorum Biography of an extinct Azorean petrel',
        
        # Default fallback
        'unknown': 'Unknown Document'
    }
    
    base_name = os.path.basename(source_file) if source_file else 'unknown'
    return filename_mapping.get(base_name, base_name.replace('_', ' ').replace('-', ' ').title())


def summarize_fact_check(question, retrieved_docs, ai_answer, language="English"):
    """
    对 Fact-Check 内容进行智能摘要
    
    Args:
        question: 用户问题
        retrieved_docs: 检索到的文档列表
        ai_answer: AI 的回答
        language: 语言（English/Portuguese）
    
    Returns:
        str: 总结性文本
    """
    # 提取文档内容
    doc_contents = []
    sources = []
    
    for i, doc in enumerate(retrieved_docs[:3], 1):  # 最多使用3个文档
        content = doc.page_content[:500]  # 每个文档最多500字符
        source = doc.metadata.get('source_file', 'Unknown')
        page = doc.metadata.get('page', 'N/A')

        friendly_name = get_friendly_filename(source)
        
        doc_contents.append(f"[Source {i}: {friendly_name}, Page {page}]\n{content}")
        sources.append(f"{friendly_name} (p.{page})")
    
    combined_docs = "\n\n".join(doc_contents)
    
    # 构建摘要 Prompt
    if language == "Portuguese":
        prompt = f"""
        Tu és um verificador de factos científico. Com base nos documentos fornecidos, cria um resumo claro e conciso.

        **Pergunta do utilizador:** {question}

        **Resposta da IA:** {ai_answer}

        **Documentos de referência:**
        {combined_docs}

        **Tua tarefa:**
        1. Resume os pontos-chave dos documentos que apoiam a resposta
        2. Menciona dados específicos (números, locais, datas) se disponíveis
        3. Mantém o resumo abaixo de 100 palavras
        4. Usa linguagem simples e clara
        5. Se os documentos não apoiam a resposta, indica isso

        **Resumo factual:**
        """
    else:
        prompt = f"""
        You are a scientific fact-checker. Based on the provided documents, create a clear and concise summary.

        **User's Question:** {question}

        **AI's Answer:** {ai_answer}

        **Reference Documents:**
        {combined_docs}

        **Your Task:**
        1. Summarize key points from the documents that support the answer
        2. Mention specific data (numbers, locations, dates) if available
        3. Keep the summary under 100 words
        4. Use simple, clear language
        5. If documents don't support the answer, indicate that

        **Factual Summary:**
        """
    
    # 使用 Qwen LLM 生成摘要
    try:
        api_key = os.getenv("DASHSCOPE_API_KEY")
        llm = Tongyi(
            model_name=os.getenv("QWEN_MODEL_NAME", "qwen-turbo"),
            temperature=0.3,  # 较低温度，确保事实性
            dashscope_api_key=api_key
        )
        
        summary = llm.invoke(prompt)
        
        # 添加来源引用
        if language == "Portuguese":
            source_text = f"\n\n📚 **Fontes:** {', '.join(sources)}"
        else:
            source_text = f"\n\n📚 **Sources:** {', '.join(sources)}"
        
        return summary.strip() + source_text
    
    except Exception as e:
        print(f"[Fact-Check] 摘要生成失败: {str(e)}")
        # 降级：返回简化的文档内容
        source = retrieved_docs[0].metadata.get('source_file', 'Unknown')
        page = retrieved_docs[0].metadata.get('page', 'N/A')
        friendly_name = get_friendly_filename(source)
        
        if language == "Portuguese":
            return f"📄 Informação extraída dos documentos:\n\n{retrieved_docs[0].page_content[:200]}...\n\n📚 Fonte: {friendly_name} (p.{page})"
        else:
            return f"📄 Information from documents:\n\n{retrieved_docs[0].page_content[:200]}...\n\n📚 Source: {friendly_name} (p.{page})"


def optimize_search_query(question, retrieved_docs):
    """
    基于用户问题和 RAG 检索内容优化搜索查询
    
    Args:
        question: 用户原始问题
        retrieved_docs: RAG 检索到的文档
    
    Returns:
        str: 优化后的搜索查询
    """
    # 从 RAG 文档中提取关键概念
    rag_keywords = set()
    for doc in retrieved_docs[:2]:  # 只看前2个最相关的文档
        content = doc.page_content.lower()
        # 提取关键生物学/保护相关词汇
        bio_keywords = ['seabird', 'petrel', 'bird', 'endemic', 'madeira', 'conservation', 
                        'endangered', 'breeding', 'nesting', 'habitat', 'species', 'population']
        for keyword in bio_keywords:
            if keyword in content:
                rag_keywords.add(keyword)
    
    # 构建精准搜索查询
    base_query = "Zino's Petrel"
    
    # 添加相关上下文关键词
    if 'conservation' in rag_keywords or 'endangered' in rag_keywords:
        base_query += " conservation status"
    elif 'breeding' in rag_keywords or 'nesting' in rag_keywords:
        base_query += " breeding habitat"
    elif 'madeira' in rag_keywords:
        base_query += " Madeira island"
    else:
        base_query += " seabird biology"
    
    # 添加英文关键词确保搜索质量
    base_query += " bird species"
    
    return base_query


def filter_search_results(results, question):
    """
    智能过滤搜索结果，排除无关内容
    
    Args:
        results: 原始搜索结果列表
        question: 用户问题
    
    Returns:
        list: 过滤后的相关结果
    """
    filtered = []
    
    # 相关关键词（生物学/保护相关）
    relevant_keywords = [
        'petrel', 'bird', 'seabird', 'species', 'madeira', 'conservation', 
        'endangered', 'breeding', 'habitat', 'ornithology', 'wildlife',
        'pterodroma', 'freira', 'endemic', 'biodiversity'
    ]
    
    # 无关关键词（技术/编程相关）
    irrelevant_keywords = [
        'framework', 'programming', 'code', 'software', 'api', 'rust',
        '编程', '框架', '开发', '代码', 'github', 'npm', 'cargo'
    ]
    
    for result in results:
        title = result.get('title', '').lower()
        body = result.get('body', '').lower()
        combined = title + ' ' + body
        
        # 检查是否包含无关关键词
        has_irrelevant = any(keyword in combined for keyword in irrelevant_keywords)
        if has_irrelevant:
            print(f"[Fact-Check] 过滤无关结果: {result.get('title', 'Unknown')[:50]}...")
            continue
        
        # 检查是否包含相关关键词
        has_relevant = any(keyword in combined for keyword in relevant_keywords)
        if has_relevant:
            filtered.append(result)
    
    return filtered


def web_search_supplement(question, retrieved_docs=None, language="English"):
    """
    智能网络搜索补充信息
    支持 DuckDuckGo（免费）和 Tavily（需 API Key）
    
    Args:
        question: 用户问题
        retrieved_docs: RAG 检索到的文档（用于优化搜索查询）
        language: 语言
    
    Returns:
        str: 网络搜索结果摘要（如果启用）
    """
    # 检查是否启用网络搜索
    use_web_search = os.getenv("USE_WEB_SEARCH", "false").lower() == "true"
    
    if not use_web_search:
        return None
    
    # 优化搜索查询（基于 RAG 上下文）
    if retrieved_docs and len(retrieved_docs) > 0:
        optimized_query = optimize_search_query(question, retrieved_docs)
        print(f"[Fact-Check] 优化搜索查询: {optimized_query}")
    else:
        optimized_query = f"Zino's Petrel {question} bird species"
    
    # 获取搜索提供商（默认 duckduckgo）
    provider = os.getenv("WEB_SEARCH_PROVIDER", "duckduckgo").lower()
    
    # 方案 1: DuckDuckGo（完全免费，无需 API Key）
    results = []  # 初始化 results 变量
    
    if provider == "duckduckgo":
        try:
            from ddgs import DDGS
            
            # 使用新版 API（无需 context manager）
            ddgs = DDGS()
            # 新版 API：参数名是 query 而不是 keywords
            raw_results = list(ddgs.text(
                query=optimized_query,
                max_results=5  # 多获取一些结果，后续过滤
            ))
            
            # 智能过滤结果
            results = filter_search_results(raw_results, question)
            print(f"[Fact-Check] 原始结果: {len(raw_results)} → 过滤后: {len(results)}")
            
            if results:
                if language == "Portuguese":
                    summary = "🌐 **Informação da Internet:**\n\n"
                else:
                    summary = "🌐 **Internet Information:**\n\n"
                
                # 只显示前2个最相关的结果
                for i, result in enumerate(results[:2], 1):
                    title = result.get('title', 'Unknown')
                    body = result.get('body', '')[:150]
                    url = result.get('href', '')
                    
                    summary += f"{i}. **{title}**\n   {body}...\n   🔗 {url}\n\n"
                
                return summary.strip()
        
        except ImportError:
            print("[Fact-Check] DDGS 未安装，运行: pip install ddgs")
        except Exception as e:
            print(f"[Fact-Check] DuckDuckGo 搜索失败: {str(e)}")
            print(f"[Fact-Check] 尝试降级到 Tavily...")
    
    # 方案 2: Tavily（需要 API Key，1000 次/月免费）
    # 如果 DuckDuckGo 失败或提供商设置为 tavily，尝试 Tavily
    if provider == "tavily" or (provider == "duckduckgo" and len(results) == 0):
        try:
            tavily_key = os.getenv("TAVILY_API_KEY")
            if tavily_key and tavily_key != "tvly-your-api-key":
                from tavily import TavilyClient
                
                client = TavilyClient(api_key=tavily_key)
                response = client.search(
                    query=f"Zino's Petrel {question}",
                    max_results=2,
                    search_depth="basic"
                )
                
                if response and 'results' in response:
                    results = response['results'][:2]
                    
                    if language == "Portuguese":
                        summary = "🌐 **Informação da Internet:**\n\n"
                    else:
                        summary = "🌐 **Internet Information:**\n\n"
                    
                    for i, result in enumerate(results, 1):
                        title = result.get('title', 'Unknown')
                        content = result.get('content', '')[:150]
                        url = result.get('url', '')
                        
                        summary += f"{i}. **{title}**\n   {content}...\n   🔗 {url}\n\n"
                    
                    return summary.strip()
        
        except ImportError:
            print("[Fact-Check] Tavily 未安装，运行: pip install tavily-python")
        except Exception as e:
            print(f"[Fact-Check] Tavily 搜索失败: {str(e)}")
    
    return None


def generate_fact_check_content(question, retrieved_docs, ai_answer, language="English"):
    """
    生成完整的 Fact-Check 内容（智能优化版）
    
    Args:
        question: 用户问题
        retrieved_docs: 检索到的文档
        ai_answer: AI 回答
        language: 语言
    
    Returns:
        str: HTML 格式的 Fact-Check 内容
    """
    # 1. 生成知识库摘要
    kb_summary = summarize_fact_check(question, retrieved_docs, ai_answer, language)
    
    # 2. 可选：智能网络搜索补充（传递 RAG 文档用于优化搜索查询）
    web_summary = web_search_supplement(
        question=question, 
        retrieved_docs=retrieved_docs,  # 传递 RAG 上下文优化搜索
        language=language
    )
    
    # 3. 组合内容
    if language == "Portuguese":
        header = "📋 **Verificação de Factos Baseada em Conhecimento Científico**\n\n"
    else:
        header = "📋 **Fact-Check Based on Scientific Knowledge**\n\n"
    
    content = header + kb_summary
    
    if web_summary:
        content += f"\n\n---\n\n{web_summary}"
    
    return content

