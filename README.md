# vectorworks-plugin-repeated-rafters

屋根の水平投影面・勾配・地廻り基準線・垂木の断面と間隔を指定すると、**VectorWorks の構造材ツール（軸組ツール）で垂木を指定間隔に並べて描画する**パスプラグインオブジェクト（PIO）です。

姉妹プロジェクト [vectorworks_plugin_import_ifc_homeskz](https://github.com/h-ikeda/vectorworks_plugin_import_ifc_homeskz) と同じ「2 フェーズ分離 + JSON 命令セット」の設計を採用しています（ジオメトリ計算フェーズは `vs` に依存せず、通常の Python 環境で単体検証できます）。

## しくみ

パスプラグインオブジェクトの**パスが屋根の水平投影面**（閉ポリゴン）になります。パラメータで指定した**基準辺**（地廻り＝軒側の辺）に対して、垂木を**直交する向き**で**指定間隔**に並べ、各垂木は基準辺（低い側）から投影面の反対側の縁（棟側）まで、投影面でクリップした長さで伸ばし、**勾配なりに傾けて**描きます（立ち上がり＝水平投影長 × 勾配 ÷ 10）。垂木は 1 本ずつ構造材ツール（`StructuralMember`）の傾斜材として描かれます。

オブジェクト（パスや各パラメータ）を編集するとリセット時に垂木が引き直されるため、屋根形状の変更に追随します。

## インストール

このリポジトリをクローンまたはダウンロードし、リポジトリのルートで以下を実行して、パッケージを VectorWorks の Python Externals フォルダにインストールします。実行時の依存ライブラリはありません。

**macOS**
```bash
pip install --target "$HOME/Library/Application Support/Vectorworks/2025/Python Externals" .
```

**Windows（コマンドプロンプト）**
```bat
pip install --target "%APPDATA%\Nemetschek\Vectorworks\2025\Python Externals" .
```

> VectorWorks のバージョンが異なる場合は `2025` の部分を実際のバージョン番号に置き換えてください。更新するときは末尾に `--upgrade` を付けて再実行します。

Python Externals フォルダは VectorWorks が自動的に `sys.path` に追加するため、インストール後は追加の設定なしにパッケージを参照できます。

## VectorWorks へのプラグイン登録

VectorWorks のプラグインマネージャで、以下の内容の**パスプラグインオブジェクト**を作成します（名前・パラメータ名は下表と厳密に一致させてください。コード側の定数は `src/vectorworks_plugin_repeated_rafters/__init__.py` 冒頭に集約しています）。

- **プラグイン名**: `垂木群`
- **オブジェクトタイプ**: パス（Path）。描いたパスが屋根の水平投影面になります。
- **オブジェクトスクリプト**: `main.py` の内容をそのまま貼り付けます。
- **パラメータ**:

  | フィールド名 | 種類 | 意味 | 既定値 |
  | --- | --- | --- | --- |
  | `Slope` | 実数 | 勾配（寸勾配。10 の水平に対する立ち上がり。例 `4` = 4/10 = 4 寸勾配） | 4 |
  | `BaseEdge` | 整数 | 地廻り基準線とするパスの辺番号（1 始まり。辺 k は頂点 k と k+1 を結ぶ） | 1 |
  | `Width` | 実数 | 垂木幅（mm、基準線方向の断面寸法） | 45 |
  | `Height` | 実数 | 垂木成（mm） | 60 |
  | `Spacing` | 実数 | 垂木の間隔（mm、基準線に沿った配置間隔） | 455 |
  | `RafterClass` | 文字 | 垂木に割り当てる作図クラス名 | `04構造-02木造-05小屋組-05垂木` |

## 使い方

1. `垂木群` ツールで屋根の水平投影面をパス（閉じた多角形）として描きます。
2. オブジェクト情報パレット（OIP）で勾配・基準辺番号・垂木断面・間隔・クラスを設定します。
3. 基準辺（地廻り＝軒側）に直交する向きで、垂木が指定間隔に並んで描画されます。

## 開発・テスト

```bash
pip install -e ".[test]"
# VectorWorks 公式 vs.py スタブを tests/ に置く（CI と同じ）
curl -fsSL https://raw.githubusercontent.com/Vectorworks/developer-scripting/main/Python/pages/files/vs.py -o tests/vs.py
mypy
pytest
```

ジオメトリ計算フェーズ（`rafters` パッケージ）は `vs` に依存しないため、垂木の並べ方・傾きの計算はスタブなしで検証できます。描画フェーズ（`vw` パッケージ）は `vs` をモックしてテストします。
