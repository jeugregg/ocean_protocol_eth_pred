import requests
import pandas as pd
from datetime import datetime, timedelta
from coinmetrics.api_client import CoinMetricsClient
# https://github.com/coinmetrics/api-client-python
# Example : https://coinmetrics.github.io/api-client-python/site/user-guide/examples.html#example-directory-current

# https://docs.coinmetrics.io/api/v4/
# https://coverage.coinmetrics.io/asset-metrics-v2/AdrActCnt?page=2
# https://coverage.coinmetrics.io/asset-metrics-v2/CapMrktCurUSD?page=2

# response = requests.get('https://api.coinmetrics.io/v4/catalog-v2/asset-metrics?pretty=true&api_key=<your_key>').json()

# response = requests.get('https://api.coinmetrics.io/v4/timeseries/asset-metrics?assets=btc&metrics=PriceUSD,FlowInGEMUSD&frequency=1d&pretty=true&api_key=<your_key>').json()
# https://coinmetrics.github.io/api-client-python/site/user-guide/examples.html#example-directory-current

# https://community-api.coinmetrics.io/v4/timeseries/asset-metrics?assets=btc&metrics=AdrActCnt&frequency=1d&pretty=true


def get_bitcoin_dominance(start_date, end_date):
    # from : https://charts.bgeometrics.com/pages-links.html
    # Dominance : https://bitcoin-data.com/api/swagger-ui/index.html#/Bitcoin%20Dominance/getBitcoinDominance
    # 30 req/hours
    # curl -X 'GET' \
    #  'https://bitcoin-data.com/v1/bitcoin-dominance?startday=2025-02-07&endday=2025-03-07' \
    #  -H 'accept: application/hal+json'
    # return df with columns[date, market_dom_BTC] , date format : YYYY-MM-DD

    # add 1 day to end_date
    end_date = (datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    url = f"https://bitcoin-data.com/v1/bitcoin-dominance?startday={start_date}&endday={end_date}"

    response = requests.get(url, headers={"accept": "application/hal+json"})
    response.raise_for_status()
    # convert from this format :
    # [
    #   {
    #     "d": "2025-02-07 00:00:00",
    #     "unixTs": "1738886400",
    #     "bitcoinDominance": "58.67"
    #   },
    #   {
    #     "d": "2025-02-08 00:00:00",
    #     "unixTs": "1738972800",
    #     "bitcoinDominance": "58.77"
    #   },
    # ]
    # to this format :
    # date	market_dom_BTC
    # 2025-02-07	58.67
    # 2025-02-08	58.77
    data = response.json()
    # convert to dataframe
    df = pd.DataFrame(data)

    # convert date to 'YYYY-MM-DD' from 2025-02-07 00:00:00+00:00
    df["date"] = pd.to_datetime(df["d"]).dt.date
    # remove d column
    df.drop(columns=["unixTs", "d"], inplace=True)
    # rename bitcoinDominance to market_dom_BTC
    df.rename(columns={"bitcoinDominance": "market_dom_BTC"}, inplace=True)
    df = df[["date", "market_dom_BTC"]]
    return df


def get_cm_bc_metrics(asset, start_date, end_date):
    """
    get active addresses with Coin Metrics
    """
    client = CoinMetricsClient()
    metrics = ["SplyCur", "AdrActCnt"]
    frequency = "1d"
    asset_metrics = client.get_asset_metrics(
        assets=asset,
        metrics=metrics,
        frequency=frequency,
        start_time=start_date,
        end_time=end_date,
    )
    df = asset_metrics.to_dataframe()
    # convert date to 'YYYY-MM-DD' from 2025-02-07 00:00:00+00:00
    df["date"] = pd.to_datetime(df["time"]).dt.date
    # remove asset and time columns
    df.drop(columns=["asset", "time"], inplace=True)
    # rename metrics
    df.rename(columns={"SplyCur": f"supply_{asset}",
              "AdrActCnt": f"act_addr_{asset}"}, inplace=True)
    # asset_metrics.export_to_csv("./data/btc_1m_asset_metrics.csv")
    # sort columns
    df = df[["date", f"supply_{asset}", f"act_addr_{asset}"]]
    # df = pd.read_csv("./data/btc_1m_asset_metrics.csv")
    return df


if __name__ == "__main__":
    asset = "BTC"
    start_date = "2025-02-07"
    end_date = "2025-03-07"
    df_onchain = get_cm_bc_metrics(asset, start_date, end_date)
    # get BTC dominance
    df_btc_dom = get_bitcoin_dominance(start_date, end_date)
    # merge df_onchain and df_btc_dom
    df_onchain = pd.merge(df_onchain, df_btc_dom, on="date")
    # save to csv
    df_onchain.to_csv("./data/btc_1m_asset_metrics.csv", index=False)
    print(df_onchain)
