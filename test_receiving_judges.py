# -*- coding: utf-8 -*-

# setup
import os
from ocean_lib.models.data_nft import DataNFT
from ocean_lib.ocean import crypto
from helpers.ocean_helpers import create_ocean_instance 
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

ocean = create_ocean_instance("polygon-test")

OCEAN = ocean.OCEAN_token
# Create Alice's wallet
from brownie.network import accounts
accounts.clear()

# Create Bob's wallet. While some flows just use Alice wallet, it's simpler to do all here.
bob_private_key = os.getenv('REMOTE_TEST_PRIVATE_KEY2')
bob = accounts.add(bob_private_key)
assert bob.balance() > 0, "Bob needs MATIC"
assert OCEAN.balanceOf(bob) > 0, "Bob needs OCEAN"

# get predicted ETH values
data_nft_addr = "0x03423C398d3eB7d63A28cb7A25Eb13b8eC59FEAA" #<addr of your data NFT. Judges will find this from the chain>
data_nft = DataNFT(ocean.config_dict, data_nft_addr)
pred_vals_str_enc = data_nft.get_data("predictions")
print(pred_vals_str_enc)
pred_vals_str = crypto.asym_decrypt(pred_vals_str_enc, bob.private_key)
print(pred_vals_str)