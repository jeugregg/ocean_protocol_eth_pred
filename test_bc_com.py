# pas ml car pas de cle api mais que BTC => pas viable si besoin de ETH et BNB
import requests

# https://www.blockchain.com/explorer/charts/n-unique-addresses
# https://www.blockchain.com/explorer/charts/market-cap
url = "https://api.blockchain.info/charts/n-transactions?timespan=30days&format=json"
response = requests.get(url)
data = response.json()

print(data)
