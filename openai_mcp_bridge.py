#!/usr/bin/env python3
"""
OpenAI APIとMCPサーバーを接続するブリッジ

OpenAI APIのfunction callingをMCPツール呼び出しに変換します。
"""

import asyncio
import json
from contextlib import AsyncExitStack
from typing import Any, Dict, List

from openai import OpenAI
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class OpenAIMCPBridge:
    """OpenAI APIとMCPサーバーを接続するブリッジクラス"""
    
    def __init__(self, openai_api_key: str, mcp_server_command: str, mcp_server_args: List[str]):
        self.client = OpenAI(api_key=openai_api_key)
        self.server_params = StdioServerParameters(
            command=mcp_server_command,
            args=mcp_server_args
        )
        self.session = None
        self.stack = None
        self.tools = []
        
    async def connect(self):
        """MCPサーバーに接続"""
        self.stack = AsyncExitStack()
        
        # stdioトランスポートを設定
        stdio_transport = await self.stack.enter_async_context(
            stdio_client(self.server_params)
        )
        read, write = stdio_transport
        
        # クライアントセッションを作成
        self.session = await self.stack.enter_async_context(
            ClientSession(read, write)
        )
        
        # 初期化
        await self.session.initialize()
        
        # ツール情報を取得してOpenAI形式に変換
        response = await self.session.list_tools()
        self.tools = self._convert_mcp_tools_to_openai(response.tools)
        
    def _convert_mcp_tools_to_openai(self, mcp_tools) -> List[Dict[str, Any]]:
        """MCPツールをOpenAI function形式に変換"""
        openai_tools = []
        
        for tool in mcp_tools:
            # MCPのinputSchemaをOpenAI形式に変換
            parameters = tool.inputSchema if hasattr(tool, 'inputSchema') else {"type": "object", "properties": {}}
            
            openai_tool = {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": parameters
                }
            }
            openai_tools.append(openai_tool)
            
        return openai_tools
    
    async def call_mcp_tool(self, name: str, arguments: Dict[str, Any]) -> str:
        """MCPツールを呼び出し"""
        result = await self.session.call_tool(
            name=name,
            arguments=arguments
        )
        
        # 結果をテキストに変換
        texts = []
        for content in result.content:
            if hasattr(content, 'text'):
                texts.append(content.text)
        
        return "\n".join(texts)
    
    async def chat_completion(self, messages: List[Dict[str, str]]) -> str:
        """OpenAI APIでチャット完了を実行（function calling対応）"""
        
        # OpenAI APIを呼び出し
        response = self.client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            tools=self.tools,
            tool_choice="auto"
        )
        
        message = response.choices[0].message
        
        # ツール呼び出しがある場合
        if message.tool_calls:
            # すべてのツール呼び出しを処理
            tool_results = []
            for tool_call in message.tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                
                # MCPツールを呼び出し
                result = await self.call_mcp_tool(function_name, function_args)
                
                tool_results.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": function_name,
                    "content": result
                })
            
            # ツール結果を含めて再度APIを呼び出し
            messages.append(message.model_dump())
            messages.extend(tool_results)
            
            final_response = self.client.chat.completions.create(
                model="gpt-4",
                messages=messages
            )
            
            return final_response.choices[0].message.content
        
        return message.content
    
    async def close(self):
        """接続を閉じる"""
        if self.stack:
            await self.stack.aclose()


async def main():
    """使用例"""
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    # ブリッジを作成
    bridge = OpenAIMCPBridge(
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        mcp_server_command="python",
        mcp_server_args=["simple_server.py"]
    )
    
    try:
        # MCPサーバーに接続
        await bridge.connect()
        print(f"利用可能なツール: {[tool['function']['name'] for tool in bridge.tools]}")
        
        # チャット例
        messages = [
            {"role": "user", "content": "get_hundredツールを使って値を取得してください。"}
        ]
        
        response = await bridge.chat_completion(messages)
        print(f"\nAIの応答: {response}")
        
    finally:
        await bridge.close()


if __name__ == "__main__":
    asyncio.run(main())