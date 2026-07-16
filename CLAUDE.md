# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## このリポジトリについて

屋根の水平投影面・勾配・地廻り基準線・垂木の断面と間隔を指定すると、**VectorWorks の構造材ツール（軸組ツール、`StructuralMember`）で垂木を指定間隔に並べて描画する**パスプラグインオブジェクト（PIO）です。

姉妹プロジェクト **vectorworks_plugin_import_ifc_homeskz**（ホームズ君 IFC インポート）の設計・規約を踏襲しています。あちらは IFC を解析して多種のオブジェクトを配置する**メニューコマンド**ですが、こちらは 1 種類のオブジェクト（垂木）だけを描く**パス PIO** です。

### 配置モデル

- **屋根の水平投影面** = PIO のパス（閉ポリゴン）。
- **地廻り基準線** = パスの 1 辺（`BaseEdge` パラメータで辺番号を 1 始まりで指定。既定は最初の辺）。
- 垂木は基準辺に**直交する向き**で、基準辺に沿って `Spacing` 間隔に並ぶ（基準辺の始点＝0 から `Spacing` の倍数の位置、両端の角を含む）。
- 各垂木は基準辺（軒＝低い側）から屋根投影面の反対側の縁（棟＝高い側）まで、投影面でクリップした長さで伸びる（**面全体**）。
- 垂木は**勾配なりに傾く**。立ち上がり ＝ 基準辺からの水平距離 × 勾配 ÷ 10。勾配は**寸勾配**（10 の水平に対する立ち上がり）。

今後、母屋・鼻母屋・広小舞などの付随要素の描画を追加する余地があります（命令セットに命令種別を足す）。

## アーキテクチャ: 2 フェーズ分離

処理は **ジオメトリ計算フェーズ** と **VectorWorks 描画フェーズ** に完全分離されている。両フェーズは JSON 直列化可能な**命令セット（ドキュメント）**だけで接続され、`vs` との密結合を避けている（姉妹プロジェクトと同じ方針）。

1. **ジオメトリ計算フェーズ（`rafters` サブパッケージ）** — `vs` に一切依存しない。屋根投影面（パス頂点列）とパラメータから、描くべき垂木を命令セット（dict）として組み立てる。通常の Python 環境で単体実行・検証できる。
2. **描画フェーズ（`vw` サブパッケージ）** — `vs` だけに依存する。命令セットを検証（`validate_document`）してから構造材ツールで垂木を描く。

命令セットのスキーマ（version・rafters 命令の形式）は `document.py` の docstring に定義されている。スキーマを変更するときは `DOCUMENT_VERSION` の互換性に注意し、`validate_document()` とテストも併せて更新すること。`run()` は両フェーズの間で `json.dumps`/`json.loads` を通すため、命令セットに直列化不能なオブジェクト（vs ハンドル等）を入れてはならない。

## パッケージ構造

```
src/
    vectorworks_plugin_repeated_rafters/   # pip インストール可能なパッケージ本体
        __init__.py           # run()（PIO オブジェクトスクリプト本体）・プラグイン名/パラメータ定数・vs 読み取りヘルパー
        document.py           # 命令セットのスキーマ定義・検証（vs 非依存）
        rafters/              # フェーズ1: ジオメトリ計算（vs 非依存）
            __init__.py       # build_document(path, ...) -> dict
            geometry.py       # 屋根投影面・基準辺・勾配・断面・間隔 → rafter 命令（ポリゴン/レイ交点計算）
        vw/                   # フェーズ2: VectorWorks 描画（vs 依存）
            __init__.py       # execute_document(document) -> 実行数 dict
            rafter.py         # rafter 命令 → 構造材（StructuralMember、傾斜材）
main.py                      # VectorWorks に登録する PIO オブジェクトスクリプト（import + run）
tests/                       # pytest 用テスト（CI は vs.py スタブを GitHub からダウンロード）
pyproject.toml               # パッケージメタデータ
```

`vs` を import してよいのは `vw` サブパッケージ内・`run()` 関数内だけ。`rafters` サブパッケージや `document.py` に `vs` への依存を持ち込まないこと。テストもこの分離に従う: `tests/test_rafters_geometry.py`・`tests/test_document.py` は vs モック不要、`tests/test_vw_rafter.py`・`tests/test_init.py`・`tests/test_integration.py` は vs モックで描画を検証する。

## コーディング規約: 型注釈

すべての関数・メソッド（テストコード含む）に引数と戻り値の型注釈を付ける。型検査は mypy で行い、CI で `mypy` を実行する（設定は `pyproject.toml` の `[tool.mypy]`、`disallow_untyped_defs` 有効）。

- 各モジュール先頭に `from __future__ import annotations` を置く（Python 3.9 互換を保ちつつ `list[str]` / `X | None` 構文を使うため）。
- 命令セットの型は `document.py` の `TypedDict`（`Document` / `RafterCommand`）を使う。`RafterCommand` は `class` キー（作図クラス名）が予約語のため functional 構文で定義している。スキーマ変更時は `TypedDict` 定義・docstring・`validate_document()` を同時に更新すること。
- `vs` モジュールは型スタブが存在しないため `ignore_missing_imports` で許容し、vs ハンドルは `Any` で扱う。VectorWorks 公式 `vs.py` スタブ（`tests/vs.py`）は型検査対象から除外している。`tests/__init__.py` を置くことで `vs` が `tests/vs.py` に解決されないようにし（解決されると本体の `vs.*` 呼び出しがスタブの署名で誤検知される）、`ignore_missing_imports` で `Any` 扱いにする。
- 検証前の命令セット（JSON 由来の信頼できない入力）を受ける関数（`validate_document()` / `execute_document()`）の引数は `Any` とし、検証済みの値だけを `Document` 型として扱う。

## スクリプトの実行方法

このスクリプトは単独の Python プログラムとして動作しない。**VectorWorks 内でパス PIO のオブジェクトスクリプトとして実行する必要がある**。`vs` モジュールは VectorWorks 独自の Python スクリプト API であり、pip でインストールできない。テストは VectorWorks 公式 `vs.py` スタブをモック対象として `pytest` で実行する（`.github/workflows/test.yml` 参照）。

**PIO はオブジェクト再生成（リセット）のたびに実行される**ため、`main.py` は姉妹プロジェクトのようなネットワーク経由の自動更新を行わず、インストール済みパッケージを読み込んで `run()` を呼ぶだけにしている（更新は `pip install --upgrade` で明示的に行う）。

## 処理フロー

`run()`（PIO オブジェクトスクリプト本体、`__init__.py`）は以下の順で処理する。

1. **オブジェクト取得** — `vs.GetCustomObjectInfo()` で PIO のハンドルを得る（失敗時は何もしない）。
2. **パス読み取り** — `_read_path_points()` が `vs.GetCustomObjectPath()` → `vs.GetVertNum()` → `vs.GetPolylineVertex()`（頂点は 1 始まり）で屋根投影面の頂点列を読む。
3. **パラメータ読み取り** — `_read_parameters()` が `vs.GetRField()` で勾配・基準辺・断面・間隔・クラスを読む（空/不正は既定値）。
4. **計算（フェーズ1）** — `rafters.build_document(path, ...)` で JSON 命令セットを組み立てる。
5. **JSON 経由の受け渡し** — `json.dumps` → `json.loads` を通し直列化可能性を保証。
6. **描画（フェーズ2）** — `vw.execute_document(document)` が検証後、垂木を描画する。

### 垂木のジオメトリ計算（rafters/geometry.py）

- `_dedupe_polygon`: パス頂点の連続重複・終端の閉じ重複を除去して閉ポリゴンの頂点列にする。
- `_inward_normal(a, b, pts)`: 基準辺 a→b のポリゴン内部を向く単位法線（＝垂木の向き）。符号付き面積（巻き方向）から決め、中点をずらした点の内外判定で補正する。
- `_ray_far_intersection(origin, dir, pts)`: 基準辺上の点から内向き法線へ伸ばした半直線と、ポリゴン各辺との交点のうち**最も遠いもの**（t>ε の最大 t）。面全体を貫くため最遠の縁（棟側）までを垂木の長さにする（凸な屋根面では出口 1 点）。半直線に平行な辺は無視する。
- `build_rafter_commands`: 基準辺（`BaseEdge` を 1 始まり→0 始まりに直し頂点数で巻き込む）に沿って `Spacing` 間隔の各点で内向きにレイを飛ばし、始端（基準辺上）から最遠交点（棟側）までの垂木命令を組み立てる。立ち上がり＝交点までの距離 × 勾配÷10 を `end_elevation` に入れる。頂点 3 点未満・基準辺退化・間隔 0 以下・交点なしは空/スキップ。計算は入力順・許容誤差に対して決定的。
- `make_member_id(width, height)`: 構造材 ID `"{幅}×{成} - 垂木"`（整数寸は小数点なし）。

### 垂木の描画（vw/rafter.py）

- `draw_rafter`: `vs.CreateNurbsCurve` + `vs.AddVertex3D` で**傾きを持たせた 3D パス**（始端 (0,0,0) → 終端 (dx, dy, 立ち上がり)）を作り、矩形プロファイルとともに `vs.CreateCustomObjectPath('StructuralMember', path, profile)` で構造材を配置。`vs.ResetOrientation3D` → `vs.Move3D(x1, y1, z1)` で始端（軒側）の実位置へ移動し、`vs.SetClass` でクラスを割り当て、`MemberID`/`ProfileShape`/`MajorBreadth`/`MajorDepth`/`B`/`D` 等のレコードフィールドを設定して `vs.ResetObject`。プラグインが使えない場合は水平投影の直線にフォールバックする。
  - **傾きの与え方が姉妹プロジェクトと異なる**: 横架材インポート（`vw/member.py`）は**ストーリのあるモデル**に配置するため傾きを始端/終端の高さバインド（`SetObjectStoryBound`）で与え、パスは水平にする（パスにも Z を持たせると高さバインドが加算されて二重になるため）。こちらは**ストーリを持たない単独 PIO** の中で描くため高さバインドは使えず、代わりに**傾きをパス（3D）そのものに持たせる**。高さバインドを併用しないので二重加算は起きない。この描画挙動（3D パスの傾斜構造材が意図どおり描かれること）は **VectorWorks 上で最終確認する**（描画フェーズは他要素と同じく VW 上で検証する方針）。
- `execute_rafters`: rafter 命令のリストを順に描画し配置数を返す。垂木は PIO が置かれたレイヤにそのまま描かれるため、レイヤ切り替え（`vs.Layer`）は行わない。

## VectorWorks へのプラグイン登録（名前・パラメータの一致）

`run()` が `vs.GetRField` で読むパラメータ名・プラグイン名は VectorWorks 側の登録と一致させる必要がある。定数は `src/vectorworks_plugin_repeated_rafters/__init__.py` 冒頭に集約している（`PLUGIN_NAME`＝`垂木群`、`PARAM_SLOPE`/`PARAM_BASE_EDGE`/`PARAM_WIDTH`/`PARAM_HEIGHT`/`PARAM_SPACING`/`PARAM_CLASS`）。登録手順・パラメータ表は `README.md` を参照。

## 開発プロセス: PR 作成と監視

コード修正を実施する際は以下のプロセスに従う（姉妹プロジェクトと同じ）:

1. **PR 作成の判断基準**: コード編集後、ユーザーに確認すべき疑義が特にない場合は自動的に PR を作成する。迷いや未確定事項がある場合は PR 作成を保留し先にユーザーに確認する。
2. **PR 作成後の対応**: `subscribe_pr_activity` で CI 結果とレビューコメントを監視する。CI 失敗は原因を診断して修正コミットを push する。軽微な指摘は自動で追加コミット、大きな設計判断が必要な指摘はユーザーに確認する。CI が全て green でレビュー上の問題もなければ自動的にマージする。
3. **コミットメッセージ**: Claude セッション URL を追加する形式: `https://claude.ai/code/session_<SESSION_ID>`
