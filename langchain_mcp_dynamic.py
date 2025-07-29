#!/usr/bin/env python3
"""
LangChainで動的にMCPツールを追加する例

MCPサーバーから自動的にツールを検出してLangChainに追加します。
"""

import asyncio
from typing import Any, Dict
from contextlib import AsyncExitStack

from langchain_openai import ChatOpenAI
from langchain_core.tools import StructuredTool
from langchain.agents import create_openai_tools_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class MCPToolWrapper:
    """MCPツールをLangChainツールとしてラップするクラス"""
    
    def __init__(self):
        self.session = None
        self.stack = None
        self.tools = []
        
    async def connect(self, command: str, args: list):
        """MCPサーバーに接続"""
        self.stack = AsyncExitStack()
        
        server_params = StdioServerParameters(command=command, args=args)
        
        stdio_transport = await self.stack.enter_async_context(
            stdio_client(server_params)
        )
        read, write = stdio_transport
        
        self.session = await self.stack.enter_async_context(
            ClientSession(read, write)
        )
        
        await self.session.initialize()
        
        # MCPツールを動的に取得してLangChainツールに変換
        await self._create_langchain_tools()
        
    async def _create_langchain_tools(self):
        """MCPツールをLangChainツールに変換"""
        response = await self.session.list_tools()
        
        for mcp_tool in response.tools:
            # MCPツールを呼び出す関数を作成
            async def call_mcp_tool(tool_name=mcp_tool.name, **kwargs):
                result = await self.session.call_tool(
                    name=tool_name,
                    arguments=kwargs
                )
                
                # 結果からテキストを抽出
                texts = []
                for content in result.content:
                    if hasattr(content, 'text'):
                        texts.append(content.text)
                
                return "\n".join(texts) if texts else "No result"
            
            # LangChainのStructuredToolとして作成
            langchain_tool = StructuredTool(
                name=mcp_tool.name,
                description=mcp_tool.description,
                func=lambda **kwargs, fn=call_mcp_tool: asyncio.create_task(fn(**kwargs)),
                coroutine=call_mcp_tool
            )
            
            self.tools.append(langchain_tool)
    
    async def close(self):
        """接続を閉じる"""
        if self.stack:
            await self.stack.aclose()


async def main():
    """メイン処理"""
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    # MCPツールラッパーを作成
    mcp_wrapper = MCPToolWrapper()
    
    try:
        # MCPサーバーに接続（自動的にツールを検出）
        await mcp_wrapper.connect("python", ["simple_server.py"])
        print(f"検出されたMCPツール: {[tool.name for tool in mcp_wrapper.tools]}")
        
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
        
        # エージェントの作成（MCPツールを使用）
        agent = create_openai_tools_agent(llm, mcp_wrapper.tools, prompt)
        agent_executor = AgentExecutor(
            agent=agent, 
            tools=mcp_wrapper.tools, 
            verbose=True
        )
        
        # テスト実行
        result = await agent_executor.ainvoke({
            "input": "get_hundredツールを使って値を取得してください。"
        })
        
        print(f"\n結果: {result['output']}")
        
    finally:
        await mcp_wrapper.close()


if __name__ == "__main__":
    asyncio.run(main())