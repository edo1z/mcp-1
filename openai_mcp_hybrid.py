#!/usr/bin/env python3
"""
OpenAI APIの通常のツールとMCPサーバーを混在させるハイブリッドシステム

通常のPython関数とMCPサーバーのツールを統合して使用できます。
"""

import asyncio
import json
from contextlib import AsyncExitStack
from typing import Any, Callable, Dict, List, Optional, Tuple

from openai import OpenAI
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class MCPServerConnection:
    """単一のMCPサーバーへの接続を管理"""
    
    def __init__(self, name: str, command: str, args: List[str]):
        self.name = name
        self.server_params = StdioServerParameters(command=command, args=args)
        self.session = None
        self.stack = None
        self.tools = []
        
    async def connect(self):
        """MCPサーバーに接続"""
        self.stack = AsyncExitStack()
        
        stdio_transport = await self.stack.enter_async_context(
            stdio_client(self.server_params)
        )
        read, write = stdio_transport
        
        self.session = await self.stack.enter_async_context(
            ClientSession(read, write)
        )
        
        await self.session.initialize()
        
        # ツール情報を取得
        response = await self.session.list_tools()
        self.tools = response.tools
        
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """ツールを呼び出し"""
        result = await self.session.call_tool(name=tool_name, arguments=arguments)
        
        texts = []
        for content in result.content:
            if hasattr(content, 'text'):
                texts.append(content.text)
        
        return "\n".join(texts)
    
    async def close(self):
        """接続を閉じる"""
        if self.stack:
            await self.stack.aclose()


class HybridToolSystem:
    """通常のツールとMCPサーバーを統合するシステム"""
    
    def __init__(self, openai_api_key: str):
        self.client = OpenAI(api_key=openai_api_key)
        self.mcp_servers: Dict[str, MCPServerConnection] = {}
        self.native_tools: Dict[str, Callable] = {}
        self.all_tools = []
        
    def add_native_tool(self, name: str, description: str, parameters: Dict[str, Any], 
                       function: Callable):
        """通常のPython関数をツールとして追加"""
        self.native_tools[name] = function
        
        tool_def = {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": parameters
            }
        }
        self.all_tools.append(tool_def)
        
    async def add_mcp_server(self, server_name: str, command: str, args: List[str], 
                           tool_prefix: Optional[str] = None):
        """MCPサーバーを追加（オプションでプレフィックス付き）"""
        server = MCPServerConnection(server_name, command, args)
        await server.connect()
        
        self.mcp_servers[server_name] = server
        
        # MCPツールをOpenAI形式に変換して追加
        for tool in server.tools:
            # プレフィックスを付ける場合
            tool_name = f"{tool_prefix}_{tool.name}" if tool_prefix else tool.name
            
            # 名前の衝突を防ぐ
            if tool_name in self.native_tools or any(t['function']['name'] == tool_name for t in self.all_tools):
                tool_name = f"{server_name}_{tool.name}"
            
            parameters = tool.inputSchema if hasattr(tool, 'inputSchema') else {"type": "object", "properties": {}}
            
            tool_def = {
                "type": "function",
                "function": {
                    "name": tool_name,
                    "description": f"[MCP:{server_name}] {tool.description}",
                    "parameters": parameters,
                    "_mcp_server": server_name,  # メタデータとして保存
                    "_mcp_original_name": tool.name
                }
            }
            self.all_tools.append(tool_def)
    
    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """ツールを実行（ネイティブまたはMCP）"""
        
        # ネイティブツールの場合
        if tool_name in self.native_tools:
            result = await self.native_tools[tool_name](arguments)
            return str(result)
        
        # MCPツールの場合
        for tool in self.all_tools:
            if tool['function']['name'] == tool_name and '_mcp_server' in tool['function']:
                server_name = tool['function']['_mcp_server']
                original_name = tool['function']['_mcp_original_name']
                
                server = self.mcp_servers[server_name]
                return await server.call_tool(original_name, arguments)
        
        raise ValueError(f"Unknown tool: {tool_name}")
    
    async def chat_completion(self, messages: List[Dict[str, str]]) -> str:
        """ハイブリッドツールを使用してチャット完了"""
        
        # クリーンなツール定義（メタデータを除去）
        clean_tools = []
        for tool in self.all_tools:
            clean_tool = {
                "type": tool["type"],
                "function": {
                    "name": tool["function"]["name"],
                    "description": tool["function"]["description"],
                    "parameters": tool["function"]["parameters"]
                }
            }
            clean_tools.append(clean_tool)
        
        # OpenAI APIを呼び出し
        response = self.client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            tools=clean_tools,
            tool_choice="auto"
        )
        
        message = response.choices[0].message
        
        # ツール呼び出しがある場合
        if message.tool_calls:
            tool_results = []
            
            for tool_call in message.tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                
                # ツールを実行
                result = await self.execute_tool(function_name, function_args)
                
                tool_results.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": function_name,
                    "content": result
                })
            
            # 結果を含めて再度APIを呼び出し
            messages.append(message.model_dump())
            messages.extend(tool_results)
            
            final_response = self.client.chat.completions.create(
                model="gpt-4",
                messages=messages
            )
            
            return final_response.choices[0].message.content
        
        return message.content
    
    async def close(self):
        """すべての接続を閉じる"""
        for server in self.mcp_servers.values():
            await server.close()


# 使用例：通常のPython関数
async def get_current_time(args: Dict[str, Any]) -> str:
    """現在時刻を取得"""
    import datetime
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


async def calculate_square(args: Dict[str, Any]) -> str:
    """数値の二乗を計算"""
    number = args.get("number", 0)
    return str(number ** 2)


async def main():
    """使用例"""
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    # ハイブリッドシステムを作成
    system = HybridToolSystem(openai_api_key=os.getenv("OPENAI_API_KEY"))
    
    # 通常のPython関数を追加
    system.add_native_tool(
        name="get_current_time",
        description="現在時刻を取得します",
        parameters={"type": "object", "properties": {}},
        function=get_current_time
    )
    
    system.add_native_tool(
        name="calculate_square",
        description="数値の二乗を計算します",
        parameters={
            "type": "object",
            "properties": {
                "number": {"type": "number", "description": "二乗する数値"}
            },
            "required": ["number"]
        },
        function=calculate_square
    )
    
    try:
        # MCPサーバーを追加（複数可）
        await system.add_mcp_server(
            server_name="simple_server",
            command="python",
            args=["simple_server.py"],
            tool_prefix="mcp"  # mcp_get_hundredという名前になる
        )
        
        # 別のMCPサーバーも追加できる
        # await system.add_mcp_server(
        #     server_name="weather_server",
        #     command="python",
        #     args=["weather_server.py"]
        # )
        
        print("利用可能なツール:")
        for tool in system.all_tools:
            print(f"- {tool['function']['name']}: {tool['function']['description']}")
        
        # チャット例
        messages = [
            {"role": "user", "content": "現在時刻を教えて、5の二乗を計算して、MCPツールで100を取得してください。"}
        ]
        
        response = await system.chat_completion(messages)
        print(f"\nAIの応答:\n{response}")
        
    finally:
        await system.close()


if __name__ == "__main__":
    asyncio.run(main())