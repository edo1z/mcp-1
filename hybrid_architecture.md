# ハイブリッドツールシステム

通常のPython関数とMCPサーバーを統合して使用するシステムです。

## アーキテクチャ

```
                  ┌─────────────────────┐
                  │  HybridToolSystem   │
                  │                     │
                  │  ┌───────────────┐  │
                  │  │ Native Tools  │  │ ← 通常のPython関数
                  │  ├───────────────┤  │
                  │  │・get_time     │  │
                  │  │・calculate    │  │
                  │  └───────────────┘  │
                  │                     │
                  │  ┌───────────────┐  │
                  │  │  MCP Servers  │  │ ← 複数のMCPサーバー
                  │  ├───────────────┤  │
                  │  │・simple_server│  │
                  │  │・weather_api  │  │
                  │  │・database     │  │
                  │  └───────────────┘  │
                  └──────────┬──────────┘
                             │
                             ▼
                      OpenAI API に統合
```

## 主な機能

### 1. 通常のPython関数を追加

```python
# シンプルなPython関数
async def get_weather(args):
    city = args["city"]
    # 実装...
    return f"{city}の天気は晴れです"

# システムに追加
system.add_native_tool(
    name="get_weather",
    description="天気を取得",
    parameters={...},
    function=get_weather
)
```

### 2. 複数のMCPサーバーを追加

```python
# MCPサーバー1
await system.add_mcp_server(
    server_name="calculator",
    command="python",
    args=["calc_server.py"],
    tool_prefix="calc"  # calc_add, calc_multiply など
)

# MCPサーバー2
await system.add_mcp_server(
    server_name="database",
    command="python",
    args=["db_server.py"],
    tool_prefix="db"  # db_query, db_insert など
)
```

### 3. 名前の衝突を防ぐ

- **プレフィックス**: `tool_prefix`で名前空間を分離
- **自動リネーム**: 衝突時はサーバー名を付加
- **メタデータ**: 内部でMCPサーバーを追跡

## 使用例

```python
# すべてのツールが統合されてOpenAI APIで使える
response = await system.chat_completion([{
    "role": "user",
    "content": "データベースから売上を取得して、合計を計算して、天気も教えて"
}])

# 内部では：
# 1. db_query (MCPサーバー1)
# 2. calc_sum (MCPサーバー2)  
# 3. get_weather (ネイティブ関数)
# が自動的に呼ばれる
```

## メリット

- ✅ **段階的移行**: 既存のツールを残しつつMCPを追加
- ✅ **柔軟な構成**: 必要なMCPサーバーだけ選択
- ✅ **名前空間管理**: プレフィックスで整理
- ✅ **統一インターフェース**: OpenAI APIで全ツール利用可

## 実装のポイント

1. **ツールの識別**
   - ネイティブ: 辞書で管理
   - MCP: メタデータで追跡

2. **実行の振り分け**
   ```python
   if tool_name in native_tools:
       # Python関数を直接実行
   else:
       # MCPサーバーに転送
   ```

3. **エラーハンドリング**
   - 各MCPサーバーの接続状態を管理
   - ツール実行エラーを適切に処理