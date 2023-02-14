# -*- coding: utf-8 -*-
import os

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())
from web3 import Web3


api_url = os.getenv("WEB3_PROVIDER_URI")
api_key = os.getenv("WEB3_PROVIDER_KEY")


# Créez une instance de Web3
w3 = Web3(Web3.HTTPProvider(f"{api_url}{api_key}"))

# Vérifiez que la connexion est établie
if w3.isConnected():
    print("Connecté à Etherscan.")
else:
    print("Connexion échouée.")

