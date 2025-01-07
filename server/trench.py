import json
import os
import re
import sqlite3
import time
import traceback
import anthropic
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException, NoSuchElementException

# This script allows AI to trade tokens on memescope through browser automation.

# Start the browser
driver = uc.Chrome(user_data_dir="./chrome-data")
driver.set_window_size(1140, 1000)

# Connect and initialize the database
connection = sqlite3.connect("trenchy.db")
cursor = connection.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message TEXT NOT NULL,
    category TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")
connection.commit()

# Initialize AI
llm = anthropic.Anthropic(api_key=os.environ['ANTHROPIC_KEY'])
system = os.environ.get('LLM_SYSTEM_PROMPT')

# Don't research the same token twice
seen_tokens = set()

# Main loop through scanning, researching, buying, and selling tokens
def main():
    while True:
        try:
            # Scan new tokens, and find one that looks interesting
            token, reason = scan()
            insert_message(f"I'm researching ${token['ticker']} ({token['name']}), {token['contract_address']}.\n\n{reason}", "researching")

            # Research the token further, and decide whether to buy it
            shouldBuy, reason = research(token, reason)
            insert_message(f"I've decided {'to buy' if shouldBuy else 'not to buy'} ${token['ticker']} ({token['name']}), {token['contract_address']}.\n\n{reason}", "buying" if shouldBuy else "not_buying")
            if shouldBuy:
                buy('.001')

            navigate_to_memescope()
            
            # Decide whether to sell any tokens in the portfolio
            time.sleep(30)
            sell()
            navigate_to_memescope()
        except Exception:
            print(traceback.format_exc())
        finally:
            time.sleep(30)

# Scans graduated tokens, and returns one to be researched further
def scan():
    navigate_to_memescope()
    time.sleep(5)

    tokens = [t for t in extract_tokens() if t['contract_address'] not in seen_tokens]

    message = llm.messages.create(
        model="claude-3-5-sonnet-latest",
        max_tokens=1024,
        system=system,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": os.environ['LLM_SCAN_PROMPT'].format(
                        tokens=json.dumps(tokens)
                    )
                }
            ],
        }]
    )

    if (len(message.content) > 1):
        raise Exception('unexpected length ' + str(len(message.content)))

    contract_address, reason = json.loads(message.content[0].text).values()
    seen_tokens.add(contract_address)

    token = next(t for t in tokens if t['contract_address'] == contract_address)
    return token, reason

# Given a token, collects data about it and returns a decision to buy it
def research(token, reason):

    links = {}
    for href in sorted(token['links'], key=lambda x: x.startswith('https://photon-sol.tinyastro.io/en/lp/')):
        if href.startswith('https://photon-sol.tinyastro.io/en/lp/'):
            links['market_data'] = {'url': href}
        elif re.match(r'https://(www\.)?(x|twitter)\.com/search\?q=', href):
            links['twitter_search'] = {'url': href}
        elif re.match(r'https://(www\.)?(x|twitter)\.com/', href):
            links['twitter_project'] = {'url': href}
        elif not href.startswith('https://lens.google.com/'):
            links['project'] = {'url': href}

    # Collect data from each link
    for key, value in links.items():
        driver.get(value['url'])
        time.sleep(7)

        if key == 'market_data':
            links[key]['screenshots'] = [
                get_chart_screenshot('15S'),
                get_volume_screenshot()
            ]
        else:
            links[key]['screenshots'] = [driver.get_screenshot_as_base64()]

    # Give the AI new data to research
    messages = [
        {
            "role": "assistant",
            "content": [{
                "type": "text",
                "text": f"I'm researching {token['ticker']} ({token['name']}), {token['contract_address']}. {reason}"
            }]
        },
        {
            "role": "user",
            "content": [
                *[{
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": screenshot,
                    },
                } for link_data in links.values() for screenshot in link_data['screenshots']],
                {
                    "type": "text",
                    "text": os.environ['LLM_RESEARCH_PROMPT'].format(
                        ticker=token['ticker'],
                        token_info=json.dumps(token),
                        websites=', '.join(links.keys()),
                        market_data=json.dumps(get_market_data()),
                        top_holders=json.dumps(get_top_holders())
                    )
                }
            ],
        }
    ]

    message = llm.messages.create(
        model="claude-3-5-sonnet-latest",
        max_tokens=1024,
        system=system,
        messages=messages
    )

    if (len(message.content) > 1):
        raise Exception('unexpected length ' + str(len(message.content)))

    return json.loads(message.content[0].text).values()

# Buys the token on the current memescope page
def buy(amount):
    amount_input = driver.find_element(By.XPATH, "//input[@placeholder='Amount to buy in SOL']")
    amount_input.send_keys(amount)
    buy_button = driver.find_element(By.XPATH, "//button[.//text()[contains(., 'Quick Buy')]]")
    buy_button.click()
    time.sleep(10)

# Decides whether to sell any tokens in the portfolio
def sell():
    driver.get('https://photon-sol.tinyastro.io/en/my_holdings')
    time.sleep(5)
    
    # Extract current holdings
    holdings = [{
        'token_name': cols[0].find_element(By.CSS_SELECTOR, "a.c-holdings__button").text.strip(),
        'liquidity_pool_url': cols[0].find_element(By.CSS_SELECTOR, "a.c-holdings__button").get_attribute("href"),
        "contract_address": cols[0].find_element(By.CLASS_NAME, "js-copy-to-clipboard").get_attribute("data-address"),
        "amount_invested_sol": cols[2].text.strip(),
        "remaining_amount_sol": cols[3].text.strip().split("\n")[0],
        "amount_sold_sol": cols[4].text.strip().split("\n")[0],
        "change_in_pnl_percent": cols[5].find_element(By.CSS_SELECTOR, "span").text.strip(),
        "change_in_pnl_absolute": cols[5].find_element(By.CLASS_NAME, "c-trades-table__td__sub").text.strip(),
    } for row in driver.find_elements(By.CSS_SELECTOR, '.u-position-relative')
      for cols in [row.find_elements(By.CLASS_NAME, "c-grid-table__td")]]

    # Ask the AI if any tokens look sellable
    messages = [{
        "role": "user",
        "content": [{
            "type": "text",
            "text": os.environ['LLM_SELL_CONSIDER_PROMPT'].format(
                holdings=json.dumps(holdings)
            )
        }],
    }]

    message = llm.messages.create(
        model="claude-3-5-sonnet-latest",
        max_tokens=1024,
        system=system,
        messages=messages
    )

    messages.append({
        "role": "assistant",
        "content": message.content
    })

    # For each token the AI is considering selling
    for seller in json.loads(message.content[0].text):
        insert_message(f"I'm considering selling {seller['token_name']}, {seller['contract_address']}.\n\n{seller['reason']}", "considering_selling")

        driver.get(seller['liquidity_pool_url'])
        time.sleep(5)

        # Give the AI additional data about the position
        messages.append({
            "role": "user",
            "content": [
                *[{
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": screenshot,
                    },
                } for screenshot in [get_chart_screenshot('1'), get_volume_screenshot()]],
                {
                    "type": "text",
                    "text": os.environ['LLM_SELL_DECISION_PROMPT'].format(
                        token_name=seller['token_name'],
                        market_data=json.dumps(get_market_data()),
                        top_holders=json.dumps(get_top_holders())
                    )
                }
            ],
        })

        message = llm.messages.create(
            model="claude-3-5-sonnet-latest",
            max_tokens=1024,
            system=system,
            messages=messages
        )
        messages.pop()

        sell, reason = json.loads(message.content[0].text).values()
        insert_message(f"I've decided {'to sell' if sell else 'not to sell'} {seller['token_name']} ({seller['contract_address']}).\n\n{reason}", "selling" if sell else "not_selling")

        # Sell if the AI decided to sell
        if sell:
            tabs = driver.find_element(By.CLASS_NAME, 'p-show__widget__tabs')
            tabs.find_element(By.CSS_SELECTOR, '[data-tab-id="sell"]').click()
            time.sleep(1)
            driver.find_element(By.CSS_SELECTOR, '.p-show .js-price-form [data-value="100"]').click()
            time.sleep(1)
            driver.find_element(By.CSS_SELECTOR, '.p-show .js-sell-btn').click()
            time.sleep(10)

# Navigates to memescope with a 2 column view (about to graduate + graduated)
def navigate_to_memescope():
    driver.get('https://photon-sol.tinyastro.io/en/memescope')
    WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.CLASS_NAME, 'l-col-xl-4')))
    driver.execute_script("""
        document.querySelectorAll('.l-col-xl-4').forEach((element, index) => {
            if (index ===0) {
                element.remove();
            } else {
                element.classList.remove('l-col-xl-4');
                element.classList.add('l-col-xl-6');
            }
        });
    """)


def extract_tokens():
    def tooltip(t, allow_missing=False):
        try:
            element = token.find_element(By.CSS_SELECTOR, f'[data-tooltip-content="{t}"]')
            parent = element.find_element(By.XPATH, "..")
            return re.sub(r'^' + re.escape(element.text), '', parent.text).strip()
        except NoSuchElementException:
            if allow_missing:
                return None
            else:
                raise

    tokens = []

    graduated = driver.find_element(By.XPATH, "//h2[text()='Graduated']/ancestor::*[4]")
    for token in graduated.find_elements(By.XPATH, './/a[starts-with(@href, "/en/lp/")]/parent::*'):
        try:
            names = token.find_elements(By.CSS_SELECTOR, '.text-ellipsis')
            token_data = {
                'ticker':  names[0].text,
                'name': names[1].text,
                'contract_address': names[1].get_attribute('data-address'),
                # Only trenching bonded tokens for now
                # 'percentage_bonded': token.find_element(By.CSS_SELECTOR,'[data-tooltip-content$="%"]').get_attribute('data-tooltip-content'),
                'percentage_owned_by_top_10_holders': tooltip('Top 10 Holders'),
                'number_of_holders': tooltip('Holders'),
                'total_trading_volume': tooltip('Volume'),
                'market_cap': tooltip('Mkt Cap'),
                'links': [
                    link.get_attribute('href') for link in token.find_elements(By.CSS_SELECTOR, 'a')
                    # Links not yet supported for research
                    if not link.get_attribute('href').startswith('https://lens.google.com/')
                    and not link.get_attribute('href').startswith('https://t.me/')
                    and not link.get_attribute('href').startswith('https://pump.fun/')
                ],
            }

            # Optional fields
            dev_sold = tooltip('Dev Sold', allow_missing=True)
            if dev_sold is not None:
                token_data['token_creator_sold_all_their_tokens'] = True
            
            dev_holdings = tooltip('Dev Holdings', allow_missing=True)
            if dev_holdings is not None:
                token_data['percentage_owned_by_token_creator'] = '0%' if dev_holdings == '' else dev_holdings

            insider_holding = tooltip('Insider Holding', allow_missing=True)
            if insider_holding is not None:
                token_data['percentage_owned_by_insiders'] = insider_holding
            
            token_bought_via_trading = tooltip('Bought via trading bot/platform & still holding', allow_missing=True)
            if token_bought_via_trading is not None:
                token_data['number_of_holders_bought_via_trading_bot_and_still_holding'] = token_bought_via_trading

            tokens.append(token_data)
        except StaleElementReferenceException:
            pass

    return tokens

# Changes chart interval and returns a screenshot.
# interval: 1S, 15S, 30S, 1, 5, 15, 30, 60, 240
def get_chart_screenshot(interval):
    driver.switch_to.frame(driver.find_element(By.TAG_NAME, "iframe"))
    intervals = driver.find_element(By.ID, 'header-toolbar-intervals')
    intervals.find_element(By.CSS_SELECTOR, '[data-role="button"]').click()
    time.sleep(1)
    interval_button = driver.find_element(By.CSS_SELECTOR, f'[data-value="{interval}"]')
    interval_button.click()
    time.sleep(3)
    driver.switch_to.default_content()
    return driver.find_element(By.CSS_SELECTOR, '.c-chart-box').screenshot_as_base64

# Returns a screenshot of the token's volume panel
def get_volume_screenshot():
    return driver.find_element(By.CSS_SELECTOR, '.p-show__info').screenshot_as_base64

# Extracts the token's market data panel
def get_market_data():
    market_data = driver.find_element(By.CSS_SELECTOR, '.p-show__pair')
    return {
        'price_usd': market_data.find_element(By.CSS_SELECTOR, '[data-cable-val="priceUsd"]').get_attribute("data-value"),
        'price_sol': market_data.find_element(By.CSS_SELECTOR, '[data-cable-val="priceQuote"]').get_attribute("data-value"),
        'token_supply': market_data.find_element(By.XPATH, "//div[contains(text(), 'Supply')]/following-sibling::div").text.strip(),
        'liquidity_usd': market_data.find_element(By.CSS_SELECTOR, '[data-cable-val="usdLiquidity"]').get_attribute("data-value"),
        'market_cap_usd': market_data.find_element(By.CSS_SELECTOR, '[data-cable-val="mktCapVal"]').get_attribute("data-value")
    }

# Extracts the token's top holders
def get_top_holders():
    return [{
        "is_liquidity_pool": len(cols[0].find_elements(By.CSS_SELECTOR, ".c-tag--pink")) > 0,
        "account": cols[0].find_element(By.TAG_NAME, "a").get_attribute('href').split('/')[-1],
        "percentage": cols[1].find_element(By.TAG_NAME, "span").text,
        "amount": cols[2].find_element(By.TAG_NAME, "span").text,
        "value": cols[3].find_element(By.TAG_NAME, "div").text,
    } for row in driver.find_elements(By.CSS_SELECTOR, ".c-grid-table__tr")[:10]
      for cols in [row.find_elements(By.CSS_SELECTOR, ".c-grid-table__td")]]

# Inserts a message into the database
def insert_message(message, category):
    cursor.execute("INSERT INTO messages (message, category) VALUES (?, ?)", (message, category))
    connection.commit()
    print(message)
    print()

if __name__ == '__main__':
    main()
