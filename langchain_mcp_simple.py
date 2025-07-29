#!/usr/bin/env python3
"""
LangChainのOpenAI LLMでMCPサーバーを使う超シンプル例

LangChainのツールとして、MCPサーバーのツールをラップします。
"""

import asyncio
from typing import Any, Dict
from contextlib import AsyncExitStack

from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain.agents import create_openai_tools_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


# グローバル変数（実際のアプリではクラスにするべき）
mcp_session = None
mcp_stack = None


async def setup_mcp_connection():
    """MCPサーバーへの接続をセットアップ"""
    global mcp_session, mcp_stack
    
    mcp_stack = AsyncExitStack()
    
    server_params = StdioServerParameters(
        command="python",
        args=["simple_server.py"]
    )
    
    stdio_transport = await mcp_stack.enter_async_context(
        stdio_client(server_params)
    )
    read, write = stdio_transport
    
    mcp_session = await mcp_stack.enter_async_context(
        ClientSession(read, write)
    )
    
    await mcp_session.initialize()


# MCPツールをLangChainツールとしてラップ
@tool
async def get_hundred_from_mcp() -> int:
    """MCPサーバーから100を取得する
    
    このツールはMCPサーバーのget_hundredツールを呼び出します。
    """
    if not mcp_session:
        raise RuntimeError("MCP connection not initialized")
    
    result = await mcp_session.call_tool(
        name="get_hundred",
        arguments={}
    )
    
    # 結果からテキストを抽出
    for content in result.content:
        if hasattr(content, 'text'):
            return int(content.text)
    
    return 0


# 通常のLangChainツール（比較用）
@tool
def add_numbers(a: int, b: int) -> int:
    """2つの数値を足し算する"""
    return a + b


async def main():
    """メイン処理"""
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    # MCPサーバーに接続
    await setup_mcp_connection()
    print("MCPサーバーに接続しました")
    
    try:
        # LangChain LLMの設定
        llm = ChatOpenAI(
            model="gpt-4",
            temperature=0,
            api_key=os.getenv("OPENAI_API_KEY")
        )
        
        # ツールのリスト（通常のツールとMCPツールを混在）
        tools = [add_numbers, get_hundred_from_mcp]
        
        # プロンプトテンプレート
        prompt = ChatPromptTemplate.from_messages([
            ("system", "あなたは便利なアシスタントです。"),
            ("user", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        
        # エージェントの作成
        agent = create_openai_tools_agent(llm, tools, prompt)
        agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)
        
        # テスト実行
        result = await agent_executor.ainvoke({
            "input": "MCPサーバーから100を取得して、それに50を足してください。"
        })
        
        print(f"\n結果: {result['output']}")
        
    finally:
        # クリーンアップ
        if mcp_stack:
            await mcp_stack.aclose()


if __name__ == "__main__":
    asyncio.run(main())