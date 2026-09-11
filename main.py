import csv
import time
from datetime import datetime
from pathlib import Path

import requests


# ============================================================
# 設定
# ============================================================

# 入力CSV
INPUT_CSV = Path("idioms.csv")

# 出力先
OUTPUT_DIR = Path("pph")

# Yahoo!リアルタイム検索 API
API_URL = "https://search.yahoo.co.jp/realtime/api/v1/pagination"

# 1回の検索で取得する最大件数
RESULTS_PER_REQUEST = 40

# 検索キーワード
SEARCH_QUERY_TEMPLATE = (
    "#シンデレラガール総選挙2026 {idol} に投票しました！"
)

# HTTPタイムアウト（秒）
REQUEST_TIMEOUT = 10

# リクエスト間隔（秒）
# Yahoo側への負荷を抑えるため、少し間隔を空ける
REQUEST_INTERVAL_SECONDS = 0.1

# HTTPヘッダー
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://search.yahoo.co.jp/realtime/search",
}


# ============================================================
# CSV読み込み
# ============================================================

def load_idols(csv_path: Path) -> list[str]:
    """
    idioms.csvからアイドル名を読み込む。

    Parameters
    ----------
    csv_path : Path
        入力CSVのパス。

    Returns
    -------
    list[str]
        アイドル名の一覧。

    Raises
    ------
    ValueError
        idol列が存在しない場合。
    """
    idols = []

    with csv_path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        reader = csv.DictReader(file)

        if not reader.fieldnames or "idol" not in reader.fieldnames:
            raise ValueError(
                f"{csv_path} に 'idol' 列がありません。"
            )

        for row in reader:
            idol = (row.get("idol") or "").strip()

            if idol:
                idols.append(idol)

    return idols


# ============================================================
# Yahoo!リアルタイム検索
# ============================================================

def search_posts(
    session: requests.Session,
    query: str,
) -> list[dict]:
    """
    Yahoo!リアルタイム検索APIから投稿一覧を取得する。

    Parameters
    ----------
    session : requests.Session
        HTTPセッション。
    query : str
        検索キーワード。

    Returns
    -------
    list[dict]
        timeline.entry に入っている投稿一覧。

    Raises
    ------
    requests.RequestException
        HTTP通信に失敗した場合。
    ValueError
        JSONやレスポンス構造を解析できない場合。
    """
    params = {
        "p": query,
        "results": RESULTS_PER_REQUEST,
    }

    response = session.get(
        API_URL,
        params=params,
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()

    data = response.json()

    # 実際のレスポンス:
    #
    # {
    #     "data": {
    #         "timeline": {
    #             "entry": [...]
    #         }
    #     }
    # }
    try:
        entries = data["timeline"]["entry"]
    except (KeyError, TypeError) as exc:
        raise ValueError(
            "Yahoo!リアルタイム検索APIのレスポンスに "
            "data.timeline.entry がありません。"
        ) from exc

    if not isinstance(entries, list):
        raise ValueError(
            "data.timeline.entry がリストではありません。"
        )

    return entries


# ============================================================
# PPH計算
# ============================================================

def calculate_pph(
    entries: list[dict],
) -> tuple[str, str, int, float]:
    """
    投稿一覧から最古時刻・最新時刻・投稿数・PPHを計算する。

    PPH:
        投稿数 / 経過時間（時間）

    Parameters
    ----------
    entries : list[dict]
        Yahoo! APIの timeline.entry。

    Returns
    -------
    tuple[str, str, int, float]
        time_min,
        time_max,
        post_count,
        post_per_hour
    """
    # 投稿数は「createdAtが正常な投稿」ではなく、
    # timeline.entry に返ってきた件数そのものを使用する。
    post_count = len(entries)

    if post_count == 0:
        return "", "", 0, 0.0

    # createdAtはUnix timestamp（秒）
    timestamps = []

    for entry in entries:
        if not isinstance(entry, dict):
            continue

        created_at = entry.get("createdAt")

        if isinstance(created_at, (int, float)):
            timestamps.append(int(created_at))

    # createdAtが取得できなかった場合
    if not timestamps:
        return "", "", post_count, 0.0

    time_min_timestamp = min(timestamps)
    time_max_timestamp = max(timestamps)

    time_min = datetime.fromtimestamp(
        time_min_timestamp
    ).strftime("%Y-%m-%d %H:%M:%S")

    time_max = datetime.fromtimestamp(
        time_max_timestamp
    ).strftime("%Y-%m-%d %H:%M:%S")

    # 投稿数1件以下ならPPHは0
    if post_count <= 1:
        return time_min, time_max, post_count, 0.0

    # 最古～最新までの経過時間（秒）
    elapsed_seconds = (
        time_max_timestamp - time_min_timestamp
    )

    # 経過時間が0ならPPHは計算できないので0
    if elapsed_seconds <= 0:
        return time_min, time_max, post_count, 0.0

    # 秒 → 時間
    elapsed_hours = elapsed_seconds / 3600

    # PPH = 投稿数 / 経過時間（時間）
    post_per_hour = post_count / elapsed_hours

    return (
        time_min,
        time_max,
        post_count,
        round(post_per_hour, 2),
    )


# ============================================================
# 結果CSV出力
# ============================================================

def write_results(
    output_path: Path,
    results: list[dict],
) -> None:
    """
    PPH計算結果をCSVに出力する。

    Parameters
    ----------
    output_path : Path
        出力CSVのパス。
    results : list[dict]
        出力する結果。
    """
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    fieldnames = [
        "idol",
        "time_min",
        "time_max",
        "post_count",
        "post_per_hour",
    ]

    with output_path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(results)


# ============================================================
# メイン処理
# ============================================================

def main() -> None:
    """
    メイン処理。
    """
    # --------------------------------------------------------
    # アイドル一覧を読み込む
    # --------------------------------------------------------

    if not INPUT_CSV.exists():
        raise FileNotFoundError(
            f"入力ファイルが見つかりません: {INPUT_CSV}"
        )

    idols = load_idols(INPUT_CSV)

    if not idols:
        raise ValueError(
            "idioms.csv にアイドル名がありません。"
        )

    print(f"アイドル数: {len(idols)}")
    print()

    # --------------------------------------------------------
    # 検索開始
    # --------------------------------------------------------

    results = []

    with requests.Session() as session:

        for index, idol in enumerate(idols, start=1):

            query = SEARCH_QUERY_TEMPLATE.format(
                idol=idol
            )

            print(
                f"[{index}/{len(idols)}] "
                f"{idol} を検索中..."
            )

            try:
                entries = search_posts(
                    session,
                    query,
                )

                (
                    time_min,
                    time_max,
                    post_count,
                    post_per_hour,
                ) = calculate_pph(entries)

                print(
                    f"  投稿数: {post_count}, "
                    f"PPH: {post_per_hour}"
                )

                results.append(
                    {
                        "idol": idol,
                        "time_min": time_min,
                        "time_max": time_max,
                        "post_count": post_count,
                        "post_per_hour": post_per_hour,
                    }
                )

            except (
                requests.RequestException,
                ValueError,
                TypeError,
            ) as exc:

                print(
                    f"  エラー: {exc}"
                )

                # 1人の取得失敗で全体を止めない
                results.append(
                    {
                        "idol": idol,
                        "time_min": "",
                        "time_max": "",
                        "post_count": 0,
                        "post_per_hour": 0.0,
                    }
                )

            # 次の検索まで少し待つ
            if index < len(idols):
                time.sleep(REQUEST_INTERVAL_SECONDS)

    # --------------------------------------------------------
    # CSV出力
    # --------------------------------------------------------

    today = datetime.now().strftime("%Y%m%d")

    output_path = (
        OUTPUT_DIR / f"result_{today}.csv"
    )

    write_results(
        output_path,
        results,
    )

    print()
    print("処理完了")
    print(f"出力先: {output_path}")


# ============================================================
# エントリーポイント
# ============================================================

if __name__ == "__main__":
    main()