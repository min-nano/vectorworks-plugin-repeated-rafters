"""VectorWorks に登録するパス PIO のオブジェクトスクリプト本体。

実行(PIO のリセット)のたびに GitHub の ``main`` ブランチの最新コミットを
確認し、インストール済みのコミットと異なれば VectorWorks 設定フォルダ内の
Python Externals フォルダへ更新インストールしてから、プラグイン本体
(``run()``)を実行する。更新した場合はキャッシュ済みモジュールを破棄する
ため、VectorWorks を再起動しなくても次のリセットから新しいコードが使われる。
パッケージが未インストールの場合(初回起動時)は自動的に新規インストールする。

本体パッケージは **実行時依存ライブラリを持たない純 Python** のため、更新は
アーカイブ(tarball)を直接展開してインストールし、pip に依存しない
(VectorWorks 同梱の Python では pip を実行できる環境が無い場合があるため)。
姉妹プロジェクト vectorworks-plugin-rebar の ``main.py`` を踏襲しているが、
あちらは certifi 等の依存ライブラリを pip で揃える一方、こちらは依存が無いので
本体のアーカイブ展開だけで完結する。

``main`` ブランチは常にテスト済みのため、バージョン番号ではなくコミット SHA の
一致で最新かどうかを判定する。インターネットに接続できない等で確認できない
場合は、アップグレードをスキップしてインストール済みのバージョンを実行する。
更新の失敗がプラグイン本体の実行を妨げてはならない。
"""

from __future__ import annotations

import glob
import importlib
import io
import json
import os
import re
import shutil
import ssl
import sys
import tarfile
import tempfile
import urllib.request

PACKAGE_NAME = "vectorworks-plugin-repeated-rafters"
MODULE_NAME = "vectorworks_plugin_repeated_rafters"
REPOSITORY = "min-nano/vectorworks-plugin-repeated-rafters"
# GitHub REST API は匿名アクセスのレートリミットが厳しいため、制限のない
# git smart HTTP プロトコルの参照広告エンドポイントから SHA を取得する
REFS_URL = f"https://github.com/{REPOSITORY}.git/info/refs?service=git-upload-pack"
ARCHIVE_URL_TEMPLATE = f"https://github.com/{REPOSITORY}/archive/{{sha}}.tar.gz"
EXTERNALS_FOLDER_NAME = "Python Externals"
# vs.GetFolderPath の負数はユーザフォルダ系を指し、-15 は設定フォルダ
# (ユーザデータフォルダ) を返す
USER_FOLDER_SPECIFIER = -15
NETWORK_TIMEOUT_SECONDS = 10.0


def _find_python_externals() -> str | None:
    """VectorWorks 設定フォルダ内の Python Externals フォルダを検出する。

    VectorWorks は設定フォルダ内の Python Externals を sys.path に自動で
    追加するため、まず sys.path から実在するフォルダを探す。見つからない
    場合は vs API で設定フォルダを取得し、その直下を探す。誤った場所への
    インストールを避けるため、実在を確認できたフォルダだけを返す。
    """
    for entry in sys.path:
        name = os.path.basename(os.path.normpath(entry))
        if name == EXTERNALS_FOLDER_NAME and os.path.isdir(entry):
            return entry
    try:
        import vs
    except ImportError:
        return None
    user_folder = vs.GetFolderPath(USER_FOLDER_SPECIFIER)
    candidate = os.path.join(user_folder, EXTERNALS_FOLDER_NAME)
    if os.path.isdir(candidate):
        return candidate
    return None


def _is_installed(externals: str) -> bool:
    """本体パッケージが Python Externals にインストール済みか判定する。"""
    pattern = os.path.join(externals, f"{MODULE_NAME}-*.dist-info")
    return bool(glob.glob(pattern))


def _installed_commit(externals: str) -> str | None:
    """Python Externals 内のパッケージの取得元コミット SHA を返す。

    pip が dist-info に記録する direct_url.json (PEP 610) のアーカイブ URL
    から SHA を取り出す。sys.path 上の別環境にある同名パッケージを誤って
    参照しないよう、更新先である Python Externals フォルダ直下の dist-info
    だけを読む。ローカルフォルダからの手動インストール等で SHA が記録
    されていない場合や一意に定まらない場合は None を返す (= 次回オンライン
    時に main の最新コミットで再インストールされる)。
    """
    pattern = os.path.join(
        externals, f"{MODULE_NAME}-*.dist-info", "direct_url.json"
    )
    shas: set[str] = set()
    for path in glob.glob(pattern):
        try:
            with open(path, encoding="utf-8") as stream:
                text = stream.read()
        except OSError:
            continue
        match = re.search(r"/archive/([0-9a-f]{40})\.tar\.gz", text)
        if match is None:
            return None
        shas.add(match.group(1))
    if len(shas) == 1:
        return shas.pop()
    return None


# 直近のネットワーク失敗の内容 (復旧失敗ダイアログでの診断用)
_last_network_error: list[str] = []


def _ssl_contexts() -> list[ssl.SSLContext]:
    """HTTPS 用の SSL コンテキストの候補を順に返す。

    システムの証明書設定に従う既定のコンテキストを優先しつつ、
    VectorWorks 同梱の Python に CA 証明書バンドルが含まれない場合に
    備えて、pip 同梱の CA バンドル (certifi) を使うコンテキストも候補に
    加える (本パッケージは依存ライブラリを持たないため、pip._vendor に
    含まれる certifi を利用する)。
    """
    contexts: list[ssl.SSLContext] = []
    try:
        contexts.append(ssl.create_default_context())
    except Exception:
        pass
    for module_name in ("certifi", "pip._vendor.certifi"):
        try:
            certifi = importlib.import_module(module_name)
            contexts.append(ssl.create_default_context(cafile=certifi.where()))
        except Exception:
            continue
    return contexts


def _fetch(url: str) -> bytes | None:
    """URL の内容を取得する。失敗時は理由を記録して None を返す。

    証明書検証の失敗に備えて、SSL コンテキストの候補を順に試す。
    """
    request = urllib.request.Request(
        url, headers={"User-Agent": PACKAGE_NAME}
    )
    for context in _ssl_contexts():
        try:
            with urllib.request.urlopen(
                request, timeout=NETWORK_TIMEOUT_SECONDS, context=context
            ) as response:
                return bytes(response.read())
        except Exception as error:
            _last_network_error.append(f"{type(error).__name__}: {error}")
    return None


def _latest_commit() -> str | None:
    """main ブランチの最新コミット SHA を取得する。

    インターネットに接続できない等で取得に失敗した場合は None を返す。
    """
    body = _fetch(REFS_URL)
    if body is None:
        return None
    text = body.decode("utf-8", errors="replace")
    match = re.search(r"([0-9a-f]{40}) refs/heads/main\b", text)
    return match.group(1) if match else None


def _extract_package(archive: tarfile.TarFile, destination: str) -> None:
    """tarball 内の src/<パッケージ> 配下のファイルを destination へ展開する。"""
    marker = f"/src/{MODULE_NAME}/"
    for member in archive.getmembers():
        if not member.isfile():
            continue
        index = member.name.find(marker)
        if index < 0:
            continue
        relative = member.name[index + len("/src/"):]
        parts = relative.split("/")
        # パストラバーサルを防ぐ
        if any(part in ("", "..") for part in parts):
            continue
        target = os.path.join(destination, *parts)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        source = archive.extractfile(member)
        if source is None:
            continue
        with source, open(target, "wb") as stream:
            shutil.copyfileobj(source, stream)


def _replace_package_dir(externals: str, staged: str) -> None:
    """展開済みの新しい本体パッケージで Python Externals 内を置き換える。

    旧バージョンをリネームして退避してからコピーし、失敗した場合は
    旧バージョンへ戻す。
    """
    target = os.path.join(externals, MODULE_NAME)
    backup = target + ".old"
    if os.path.isdir(backup):
        shutil.rmtree(backup)
    if os.path.isdir(target):
        os.rename(target, backup)
    try:
        shutil.copytree(staged, target)
    except Exception:
        shutil.rmtree(target, ignore_errors=True)
        if os.path.isdir(backup):
            os.rename(backup, target)
        raise
    shutil.rmtree(backup, ignore_errors=True)


def _write_dist_info(externals: str, archive_url: str) -> None:
    """インストール元 (コミット SHA 入り URL) を dist-info に記録する。

    pip が記録する direct_url.json (PEP 610) と同じ場所・形式にして、
    _installed_commit() が pip でのインストールと区別なく読めるように
    する。既存の dist-info は古い情報のため置き換える。
    """
    pattern = os.path.join(externals, f"{MODULE_NAME}-*.dist-info")
    for stale in glob.glob(pattern):
        shutil.rmtree(stale, ignore_errors=True)
    dist_info = os.path.join(externals, f"{MODULE_NAME}-0.0.0.dist-info")
    os.makedirs(dist_info, exist_ok=True)
    metadata = (
        "Metadata-Version: 2.1\n"
        f"Name: {PACKAGE_NAME}\n"
        "Version: 0.0.0\n"
    )
    with open(
        os.path.join(dist_info, "METADATA"), "w", encoding="utf-8"
    ) as stream:
        stream.write(metadata)
    with open(
        os.path.join(dist_info, "direct_url.json"), "w", encoding="utf-8"
    ) as stream:
        json.dump({"url": archive_url, "archive_info": {}}, stream)
    with open(
        os.path.join(dist_info, "INSTALLER"), "w", encoding="utf-8"
    ) as stream:
        stream.write("main.py\n")


def _install_package_from_archive(externals: str, sha: str) -> str | None:
    """本体パッケージをアーカイブの直接展開でインストールする。

    本体は純 Python のためビルド不要で、tarball 内の src/<パッケージ> を
    Python Externals へ展開するだけでよい。VectorWorks 同梱の Python では
    pip を実行できる環境が無い場合があるため、本体のインストール・更新は
    pip に依存しない。成功時は None、失敗時は理由のメッセージを返す。
    """
    archive_url = ARCHIVE_URL_TEMPLATE.format(sha=sha)
    data = _fetch(archive_url)
    if data is None:
        detail = _last_network_error[-1] if _last_network_error else ""
        return "本体パッケージのダウンロードに失敗しました。\n" + detail
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
                _extract_package(archive, temp_dir)
            staged = os.path.join(temp_dir, MODULE_NAME)
            if not os.path.isdir(staged):
                return "アーカイブに本体パッケージが見つかりませんでした。"
            _replace_package_dir(externals, staged)
    except Exception as error:
        return f"本体パッケージの展開に失敗しました: {error}"
    _write_dist_info(externals, archive_url)
    return None


def _purge_cached_modules() -> None:
    """キャッシュ済みの本体パッケージのモジュールを sys.modules から破棄する。

    VectorWorks はスクリプト実行間で Python インタプリタを保持するため、
    更新後も旧バージョンのモジュールが sys.modules に残る。本体は依存
    ライブラリを持たないため、破棄対象は本体パッケージのみでよい。
    """
    for name in list(sys.modules):
        if name == MODULE_NAME or name.startswith(MODULE_NAME + "."):
            del sys.modules[name]


def _prioritize_externals(externals: str) -> None:
    """Python Externals を sys.path の先頭へ移動する。

    更新判定は Python Externals 内のパッケージを基準にしているため、
    実行時の import でも sys.path の後方や別の場所にある同名パッケージ
    より Python Externals が優先されるようにする。
    """
    if externals in sys.path:
        sys.path.remove(externals)
    sys.path.insert(0, externals)


def _activate_externals(externals: str) -> None:
    """インストール直後の Python Externals を確実に参照させる。

    sys.path の優先順位を整えたうえで、キャッシュ済みの旧バージョンの
    モジュールを破棄する。
    """
    _prioritize_externals(externals)
    _purge_cached_modules()
    importlib.invalidate_caches()


def _upgrade_if_available() -> None:
    """main の最新コミットと異なるバージョンなら Python Externals へ更新する。

    本体パッケージはアーカイブの直接展開で入れ替える (pip 不要)。最新
    コミットの確認に失敗した場合 (オフライン等) や Python Externals フォルダ
    を検出できない場合は何もしない。
    """
    externals = _find_python_externals()
    if externals is None:
        return
    latest = _latest_commit()
    if latest is None or latest == _installed_commit(externals):
        # 更新は不要でも、import が別の場所の同名パッケージを拾わないよう
        # sys.path の優先順位だけは毎回整える (キャッシュは破棄しない)
        _prioritize_externals(externals)
        return
    if _install_package_from_archive(externals, latest) is not None:
        return
    _activate_externals(externals)


def _repair_install() -> str | None:
    """破損したインストールを丸ごと入れ直して復旧する。

    部分的に書き込まれたパッケージが Python Externals に残ると import が
    失敗し続けるため、main の最新コミットの本体を展開し直す。復旧できた
    場合は None、できない場合は理由のメッセージを返す。
    """
    externals = _find_python_externals()
    if externals is None:
        return "Python Externals フォルダを検出できませんでした。"
    latest = _latest_commit()
    if latest is None:
        detail = _last_network_error[-1] if _last_network_error else ""
        return (
            "GitHub から最新コミットを取得できませんでした"
            " (インターネット接続を確認してください)。\n" + detail
        )
    failure = _install_package_from_archive(externals, latest)
    if failure is not None:
        return failure
    _activate_externals(externals)
    return None


def _alert(message: str) -> None:
    """vs.AlrtDialog でメッセージを表示する (vs が無い環境では何もしない)。"""
    try:
        import vs

        vs.AlrtDialog(message)
    except Exception:
        pass


def _main() -> None:
    try:
        _upgrade_if_available()
    except Exception:
        # 更新の失敗がプラグイン本体の実行を妨げてはならない
        pass
    try:
        module = importlib.import_module(MODULE_NAME)
    except Exception:
        # 部分書き込み等でインストールが破損していると import が失敗し
        # 続けるため、強制的に再インストールして復旧を試みる
        try:
            failure = _repair_install()
        except Exception as error:
            failure = f"再インストール中にエラーが発生しました: {error}"
        if failure is not None:
            _alert(
                "プラグインの読み込みに失敗し、自動復旧もできませんでした。\n"
                + failure
            )
            raise
        module = importlib.import_module(MODULE_NAME)
    module.run()


_main()
