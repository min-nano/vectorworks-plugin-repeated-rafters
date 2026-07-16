# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## このリポジトリについて

屋根の水平投影面・勾配・地廻り基準線・垂木の断面と間隔を指定すると、**VectorWorks の構造材ツール（軸組ツール、`StructuralMember`）で垂木を指定間隔に並べて描画する**パスプラグインオブジェクト（PIO）です。

姉妹プロジェクト **vectorworks_plugin_import_ifc_homeskz**（ホームズ君 IFC インポート）の設計・規約を踏襲しています。あちらは IFC を解析して多種のオブジェクトを配置する**メニューコマンド**ですが、こちらは 1 種類のオブジェクト（垂木）だけを描く**パス PIO** です。

### 配置モデル

- **屋根の水平投影面** = PIO のパス（閉ポリゴン）。
- **地廻り基準線** = 2 つの**コントロールポイント**で指定する**内蔵の直線**。軒の出があると屋根投影面の軒側の辺は軒先であって地廻りではないため、地廻りをパスの辺で制御せず独立に置けるようにしている。コントロールポイントの座標はユニバーサル名 `ControlPoint01`／`ControlPoint02`（作成順に自動採番・固定。フィールド名では読めない）の末尾に `X`／`Y` を付けたフィールドで読む。コントロールポイント未設定（2 点が一致）なら、パスの最初の辺を基準辺に使うフォールバックに切り替える。
- 垂木は基準線に**直交する向き**で、基準線を**無限に延長した直線**に沿って `Spacing` 間隔に並ぶ（基準線の始点＝0 から `Spacing` の倍数の位置）。並ぶ**範囲は基準線の 2 端点の間に限らず**、屋根の水平投影面（パス）を基準線方向へ射影した広がりの全域とする（基準線が短くてもパス幅いっぱいに並ぶ）。各垂木は下記のとおり屋根投影面でクリップされる。
- 各垂木は地廻り基準線から**棟側（高い側）と軒先側（低い側）の両方向**へ、屋根投影面でクリップした長さで伸びる（**面全体**）。棟／軒先の向きは、基準線の中点から屋根投影面が広く伸びる側を棟、狭い側（軒の出）を軒先として**自動判定**する（コントロールポイントの始点・終点の順序に依存しない）。
- 垂木は**勾配なりに傾く**。立ち上がり ＝ 地廻り基準線からの水平距離 × 勾配 ÷ 10。勾配は**寸勾配**（10 の水平に対する立ち上がり）。高さ 0 の基準（データム）は地廻り基準線で、軒の出側（軒先）は負の高さになる。

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
            geometry.py       # 屋根投影面・地廻り基準線・勾配・断面・間隔 → rafter 命令（ポリゴン/レイ交点計算）
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

`main.py` は姉妹プロジェクト **vectorworks-plugin-rebar** と同じく、実行（PIO のリセット）のたびに GitHub の `main` ブランチの最新コミット SHA を確認し、インストール済みと異なれば Python Externals フォルダへ更新インストールしてから `run()` を呼ぶ（未インストールなら新規インストール）。ただし**本体は実行時依存ライブラリを持たない純 Python** なので、rebar のように pip で依存ライブラリを揃える機構は持たず、tarball を直接展開して本体パッケージを入れ替えるだけにしている（VectorWorks 同梱 Python では pip を実行できない場合があるため pip 非依存）。

- 最新コミットは git smart HTTP の参照広告（`.../info/refs?service=git-upload-pack`）から取得し、REST API のレートリミットを避ける。
- SHA 一致で最新判定する（`main` は常にテスト済みのためバージョン番号は使わない）。インストール元 SHA は dist-info の `direct_url.json`（PEP 610）に記録し、pip インストールと同じ方法で読む。
- 更新後は `sys.modules` の本体モジュールを破棄し、`sys.path` の先頭に Python Externals を置くので、VectorWorks を再起動せずとも次のリセットから新コードが使われる。
- オフライン等で確認・取得に失敗しても、更新をスキップしてインストール済みを実行する（更新失敗が本体実行を妨げない）。import 失敗時は `_repair_install()` で入れ直しを試み、それでも失敗した場合のみ `vs.AlrtDialog` で理由を表示する。

**PIO はオブジェクト再生成（リセット）のたびに実行される**点に注意（リセットは図形の移動・編集のたびに起きる）。開発初期は毎リセットで更新確認する方針だが、将来は更新確認を VectorWorks セッション内の初回だけに絞る余地がある（rebar のロードマップと同様）。

## 処理フロー

`run()`（PIO オブジェクトスクリプト本体、`__init__.py`）は以下の順で処理する。

1. **オブジェクト取得** — `vs.GetCustomObjectInfo()` で PIO のハンドルを得る（失敗時は何もしない）。
2. **パス読み取り** — `_read_path_points()` が `vs.GetCustomObjectPath()` → `vs.GetVertNum()` → `vs.GetPolylineVertex()`（頂点は 1 始まり）で屋根投影面の頂点列を読む。
3. **パラメータ読み取り** — `_read_parameters()` が `vs.GetRField()` で勾配・地廻り基準線（コントロールポイント）・断面・間隔・クラスを読む（空/不正は既定値）。
4. **計算（フェーズ1）** — `rafters.build_document(path, ...)` で JSON 命令セットを組み立てる。
5. **JSON 経由の受け渡し** — `json.dumps` → `json.loads` を通し直列化可能性を保証。
6. **描画（フェーズ2）** — `vw.execute_document(document)` が検証後、垂木を描画する。

### 垂木のジオメトリ計算（rafters/geometry.py）

- `_dedupe_polygon`: パス頂点の連続重複・終端の閉じ重複を除去して閉ポリゴンの頂点列にする。
- `_resolve_base_line(base_line, pts)`: 地廻り基準線の 2 端点とフリーモードか否かを返す。`base_line`（コントロールポイント 2 点）が有効（2 点が離れている）ならフリーモード、退化・未指定ならパスの最初の辺を基準辺に使うフォールバック（非フリーモード）。
- `_line_signed_intersections(origin, axis, pts)`: origin を通り axis 方向の**直線**とポリゴン各辺の符号付き交点パラメータ t のリスト。正の t は axis 方向、負は逆方向。原点自身（|t|≤ε）と平行辺は除外。地廻りから両方向へ伸ばすため半直線ではなく直線で両側を集める。
- `_choose_up_normal(mid, left, right, pts)`: 棟（高い側）を向く法線を、基準線の中点から屋根投影面が広く伸びる側で決める（狭い側が軒先＝軒の出）。同程度なら left を採用して決定的にする。
- `_projection_range(origin, axis, pts)`: パス頂点を origin 基準・axis 方向へ射影した符号付き距離の最小・最大。基準線を無限直線とみなし、垂木を並べる範囲をパスの広がりで決めるのに使う。
- `_inward_normal(a, b, pts)` / `_ray_far_intersection(origin, dir, pts)`: **フォールバック（パスの辺を基準線に使う）専用**。辺の内向き単位法線と、その内向き半直線とポリゴン各辺の最遠交点（t>ε の最大 t）。基準辺（t=0）から屋根面側の縁まで 1 方向に伸ばす（＝旧来の挙動）。
- `build_rafter_commands`: 地廻り基準線を無限直線とみなし、パスを基準線方向へ射影した広がり（`_projection_range`）の全域に始点＝0 から `Spacing` 間隔の各点（両向きの整数倍）で垂木を並べる。各点で、フリーモードは棟側の法線に沿って両方向の符号付き交点の最小 t（軒先側）〜最大 t（棟側）、フォールバックは内向き最遠交点までの垂木命令を組み立てる。`elevation`＝t_min×勾配÷10（軒先側、負になりうる）、`end_elevation`＝t_max×勾配÷10（棟側）。高さ 0 の基準は地廻り基準線（t=0）。頂点 3 点未満・基準線退化・間隔 0 以下・交点 2 未満は空/スキップ。計算は入力順・許容誤差に対して決定的。
- `make_member_id(width, height)`: 構造材 ID `"{幅}×{成} - 垂木"`（整数寸は小数点なし）。

### 垂木の描画（vw/rafter.py）

- `draw_rafter`: `vs.CreateNurbsCurve` + `vs.AddVertex3D` で**傾きを持たせた 3D パス**（始端 (0,0,0) → 終端 (dx, dy, 立ち上がり)）を作り、矩形プロファイルとともに `vs.CreateCustomObjectPath('StructuralMember', path, profile)` で構造材を配置。`vs.ResetOrientation3D` → `vs.Move3D(x1, y1, z1)` で始端（軒側）の実位置へ移動し、`vs.SetClass` でクラスを割り当て、`MemberID`/`ProfileShape`/`MajorBreadth`/`MajorDepth`/`B`/`D` 等のレコードフィールドを設定して `vs.ResetObject`。プラグインが使えない場合は水平投影の直線にフォールバックする。
  - **傾きの与え方が姉妹プロジェクトと異なる**: 横架材インポート（`vw/member.py`）は**ストーリのあるモデル**に配置するため傾きを始端/終端の高さバインド（`SetObjectStoryBound`）で与え、パスは水平にする（パスにも Z を持たせると高さバインドが加算されて二重になるため）。こちらは**ストーリを持たない単独 PIO** の中で描くため高さバインドは使えず、代わりに**傾きをパス（3D）そのものに持たせる**。高さバインドを併用しないので二重加算は起きない。この描画挙動（3D パスの傾斜構造材が意図どおり描かれること）は **VectorWorks 上で最終確認する**（描画フェーズは他要素と同じく VW 上で検証する方針）。
- `execute_rafters`: rafter 命令のリストを順に描画し配置数を返す。垂木は PIO が置かれたレイヤにそのまま描かれるため、レイヤ切り替え（`vs.Layer`）は行わない。

## VectorWorks へのプラグイン登録（名前・パラメータの一致）

`run()` が `vs.GetRField` で読むパラメータ名・プラグイン名は VectorWorks 側の登録と一致させる必要がある。定数は `src/vectorworks_plugin_repeated_rafters/__init__.py` 冒頭に集約している（`PLUGIN_NAME`＝`垂木群`、`PARAM_SLOPE`/`PARAM_WIDTH`/`PARAM_HEIGHT`/`PARAM_SPACING`/`PARAM_CLASS` と、地廻り基準線のコントロールポイント座標 `PARAM_BASE_START_X`/`PARAM_BASE_START_Y`/`PARAM_BASE_END_X`/`PARAM_BASE_END_Y`＝`ControlPoint01X`/`ControlPoint01Y`/`ControlPoint02X`/`ControlPoint02Y`）。**コントロールポイントはフィールド名を変えても座標は読めず**、ユニバーサル名 `ControlPoint01`／`ControlPoint02`（作成順に自動採番・固定）の末尾に `X`/`Y` を付けたフィールドで読む。よって地廻り基準線用のコントロールポイントを最初に 2 つ作成すること。登録手順・パラメータ表は `README.md` を参照。

## 開発プロセス: PR 作成と監視

コード修正を実施する際は以下のプロセスに従う（姉妹プロジェクトと同じ）:

1. **PR 作成の判断基準**: コード編集後、ユーザーに確認すべき疑義が特にない場合は自動的に PR を作成する。迷いや未確定事項がある場合は PR 作成を保留し先にユーザーに確認する。
2. **PR 作成後の対応**: `subscribe_pr_activity` で CI 結果とレビューコメントを監視する。CI 失敗は原因を診断して修正コミットを push する。軽微な指摘は自動で追加コミット、大きな設計判断が必要な指摘はユーザーに確認する。CI が全て green でレビュー上の問題もなければ自動的にマージする。
3. **コミットメッセージ**: Claude セッション URL を追加する形式: `https://claude.ai/code/session_<SESSION_ID>`
