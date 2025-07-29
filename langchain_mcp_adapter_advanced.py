#!/usr/bin/env python3
"""
langchain-mcp-adaptersの高度な例

複数のMCPサーバーと通常のツールを組み合わせて使用します。
"""

import asyncio
import os
from typing import Literal
from dotenv import load_dotenv

from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain.agents import create_openai_tools_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder


# 通常のLangChainツール
@tool
def calculate_area(shape: Literal["circle", "square"], size: float) -> float:
    """図形の面積を計算する
    
    Args:
        shape: 図形の種類（circle: 円、square: 正方形）
        size: 円の場合は半径、正方形の場合は一辺の長さ
    """
    if shape == "circle":
        return 3.14159 * size * size
    else:  # square
        return size * size


@tool
def get_current_time() -> str:
    """現在時刻を取得する"""
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


async def main():
    """メイン処理"""
    load_dotenv()
    
    # 複数のMCPサーバーを設定
    client = MultiServerMCPClient({
        "simple_server": {
            "command": "python",
            "args": ["simple_server.py"],
            "transport": "stdio"
        },
        # 追加のMCPサーバーの例（実際には存在しないサーバー）
        # "calculator": {
        #     "command": "python",
        #     "args": ["calculator_server.py"],
        #     "transport": "stdio"
        # },
        # "weather": {
        #     "url": "http://localhost:8000/mcp",
        #     "transport": "streamable-http",
        #     "headers": {
        #         "Authorization": f"Bearer {os.getenv('WEATHER_API_KEY')}"
        #     }
        # }
    })
    
    try:
        # MCPツールを取得
        mcp_tools = await client.get_tools()
        print(f"MCPツール: {[tool.name for tool in mcp_tools]}")
        
        # 通常のツールと組み合わせる
        native_tools = [calculate_area, get_current_time]
        all_tools = mcp_tools + native_tools
        
        print(f"すべてのツール: {[tool.name for tool in all_tools]}")
        
        # LangChain LLMの設定
        llm = ChatOpenAI(
            model="gpt-4",
            temperature=0,
            api_key=os.getenv("OPENAI_API_KEY")
        )
        
        # プロンプトテンプレート
        prompt = ChatPromptTemplate.from_messages([
            ("system", """あなたは便利なアシスタントです。
            
利用可能なツール:
- get_hundred: MCPサーバーから100を取得
- calculate_area: 図形の面積を計算
- get_current_time: 現在時刻を取得

これらのツールを組み合わせて、ユーザーの質問に答えてください。"""),
            ("user", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        
        # エージェントの作成
        agent = create_openai_tools_agent(llm, all_tools, prompt)
        agent_executor = AgentExecutor(
            agent=agent,
            tools=all_tools,
            verbose=True,
            max_iterations=5
        )
        
        # 複雑なタスクの実行
        print("\n=== 複雑なタスクの実行 ===")
        result = await agent_executor.ainvoke({
            "input": """以下のタスクを実行してください：
1. 現在時刻を取得
2. MCPサーバーから100を取得
3. 半径が取得した値（100）の円の面積を計算
4. すべての結果をまとめて報告"""
        })
        
        print(f"\n最終結果:\n{result['output']}")
        
        # ランタイムヘッダーの例（認証やトレーシング用）
        print("\n=== ランタイムヘッダーを使った例 ===")
        
        # ヘッダーを動的に設定してツールを呼び出す
        tools_with_headers = await client.get_tools(
            runtime_headers={
                "simple_server": {
                    "X-Request-ID": "12345",
                    "X-User-ID": "user-001"
                }
            }
        )
        
        # 特定のサーバーのツールだけを取得
        simple_server_tools = [t for t in tools_with_headers if t.name == "get_hundred"]
        
        if simple_server_tools:
            result = await simple_server_tools[0].ainvoke({})
            print(f"ヘッダー付きリクエストの結果: {result}")
        
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())