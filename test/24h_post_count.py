
"""Yahoo!リアルタイム検索から24時間のポスト数を取得する。"""

import re
from urllib.parse import urlencode

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


BASE_URL = "https://search.yahoo.co.jp/realtime/search"
WAIT_SECONDS = 30

# グラフ上部の合計数を取得するセレクタ
COUNT_SELECTOR = (
    "#graph div[class*='Chart_totalCount'] > p > span"
)


def get_post_count(query: str) -> int:
    """指定キーワードの24時間表示のポスト数を取得する。

    Args:
        query: Yahoo!リアルタイム検索の検索キーワード。

    Returns:
        24時間表示のポスト数。

    Raises:
        TimeoutException: 制限時間内に対象要素が見つからない場合。
        ValueError: 取得したテキストが数値ではない場合。
    """
    params = {
        "p": query,
        "gm": "d",
    }
    url = f"{BASE_URL}?{urlencode(params)}"

    options = Options()
    options.add_argument("--headless")
    options.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(options=options)

    try:
        driver.get(url)
        wait = WebDriverWait(driver, WAIT_SECONDS)

        # グラフ上部の数値が描画されるまで待つ
        element = wait.until(
            EC.visibility_of_element_located(
                (By.CSS_SELECTOR, COUNT_SELECTOR)
            )
        )

        raw_text = element.text.strip()
        normalized = raw_text.replace(",", "")

        if not re.fullmatch(r"\d+", normalized):
            raise ValueError(
                f"ポスト数を数値として解釈できません: {raw_text!r}"
            )

        return int(normalized)

    finally:
        driver.quit()


if __name__ == "__main__":
    keyword = "ライブ音源"

    try:
        count = get_post_count(keyword)
        print(f"検索キーワード: {keyword}")
        print(f"24時間のポスト数: {count:,}件")

    except TimeoutException:
        print(
            "エラー: グラフの数値が時間内に見つかりませんでした。"
            "URL、セレクタ、ページの表示状態を確認してください。"
        )

    except ValueError as error:
        print(f"エラー: {error}")
