#!/usr/bin/env python3
"""
langchain-mcp-adaptersを使った超シンプルな例

公式のMCPアダプターを使用してLangChainと連携します。
"""

import asyncio
import os
from dotenv import load_dotenv

from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from langchain.agents import create_openai_tools_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder


async def main():
    """メイン処理"""
    load_dotenv()
    
    # MCPクライアントの設定（複数サーバー対応）
    client = MultiServerMCPClient({
        "simple_server": {
            "command": "python",
            "args": ["simple_server.py"],
            "transport": "stdio"
        }
        # 他のサーバーも追加可能
        # "weather_server": {
        #     "command": "python",
        #     "args": ["weather_server.py"],
        #     "transport": "stdio"
        # }
    })
    
    try:
        # MCPツールを取得（自動的にLangChainツールに変換される）
        tools = await client.get_tools()
        print(f"利用可能なツール: {[tool.name for tool in tools]}")
        
        # LangChain LLMの設定
        llm = ChatOpenAI(
            model="gpt-4",
            temperature=0,
            api_key=os.getenv("OPENAI_API_KEY")
        )
        
        # プロンプトテンプレート
        prompt = ChatPromptTemplate.from_messages([
            ("system", "あなたは便利なアシスタントです。利用可能なツールを使って質問に答えてください。"),
            ("user", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        
        # エージェントの作成
        agent = create_openai_tools_agent(llm, tools, prompt)
        agent_executor = AgentExecutor(
            agent=agent, 
            tools=tools, 
            verbose=True
        )
        
        # テスト実行
        result = await agent_executor.ainvoke({
            "input": "get_hundredツールを使って値を取得してください。"
        })
        
        print(f"\n結果: {result['output']}")
        
    finally:
        # クライアントのクリーンアップ
        await client.close()


# LangGraphを使った例（より高度な使い方）
async def langgraph_example():
    """LangGraphを使った例"""
    from langgraph.prebuilt import create_react_agent
    
    load_dotenv()
    
    # MCPクライアントの設定
    client = MultiServerMCPClient({
        "simple_server": {
            "command": "python",
            "args": ["simple_server.py"],
            "transport": "stdio"
        }
    })
    
    try:
        # ツールを取得
        tools = await client.get_tools()
        
        # LangGraphのReActエージェントを作成
        agent = create_react_agent(
            model="openai:gpt-4",  # または "anthropic:claude-3-opus-20240229"
            tools=tools
        )
        
        # エージェントを実行
        response = await agent.ainvoke({
            "messages": [{"role": "user", "content": "get_hundredを使って100を取得してください"}]
        })
        
        # 最後のメッセージを表示
        print(f"\nエージェントの応答: {response['messages'][-1]['content']}")
        
    finally:
        await client.close()


if __name__ == "__main__":
    print("=== LangChain Agent Example ===")
    asyncio.run(main())
    
    print("\n=== LangGraph Example ===")
    asyncio.run(langgraph_example())