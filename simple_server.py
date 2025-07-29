"""
超シンプルなMCPサーバー
呼び出すと100を返すだけのサーバー
"""

from fastmcp import FastMCP

# FastMCPサーバーを作成
mcp = FastMCP("Simple 100 Server")


@mcp.tool
def get_hundred() -> int:
    """100を返すシンプルな関数
    
    このツールは常に数値の100を返します。
    パラメータは不要で、エラーも発生しません。
    テスト用の最もシンプルなツールです。
    """
    return 100


# メイン実行部分
if __name__ == "__main__":
    # stdioトランスポートでサーバーを起動
    mcp.run(transport="stdio")
