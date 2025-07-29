#!/usr/bin/env python3
"""
Simple MCPサーバーのテストクライアント
"""

import asyncio
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    """メイン関数"""
    # サーバーへの接続設定
    server_params = StdioServerParameters(command="python", args=["simple_server.py"])

    async with AsyncExitStack() as stack:
        # stdioトランスポートを設定
        stdio_transport = await stack.enter_async_context(stdio_client(server_params))
        read, write = stdio_transport

        # クライアントセッションを作成
        session = await stack.enter_async_context(ClientSession(read, write))

        # 初期化
        await session.initialize()
        print("サーバーに接続しました！")

        # 利用可能なツールを確認
        response = await session.list_tools()
        tools = response.tools
        print(f"\n利用可能なツール: {[tool.name for tool in tools]}")

        # 詳細情報を表示
        for tool in tools:
            print(f"\nツール名: {tool.name}")
            print(f"説明: {tool.description}")
            if hasattr(tool, "inputSchema"):
                print(f"入力スキーマ: {tool.inputSchema}")

        # get_hundredツールを実行
        result = await session.call_tool(name="get_hundred", arguments={})

        print(f"\n結果: {result}")

        # コンテンツの中身を表示
        for content in result.content:
            if hasattr(content, "text"):
                print(f"返された値: {content.text}")


if __name__ == "__main__":
    asyncio.run(main())

