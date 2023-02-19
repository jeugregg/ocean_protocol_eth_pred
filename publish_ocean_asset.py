# -*- coding: utf-8 -*-
import os
import time
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

# Create Ocean instance
from ocean_lib.web3_internal.utils import connect_to_network
connect_to_network("polygon-test") # mumbai is "polygon-test"

from ocean_lib.example_config import get_config_dict
from ocean_lib.ocean.ocean import Ocean
config = get_config_dict("polygon-test")
ocean = Ocean(config)



# definitions
#url = "https://app.ardrive.io/#/file/398356ae-04f9-4b22-a4e8-21a961ef3f60/view"


url = "https://app.ardrive.io/#/file/b81e592c-69a6-4b8c-8013-34ff7a6e25d6/view"


to_address="0xA54ABd42b11B7C97538CAD7C6A2820419ddF703E" #official judges address
#to_address = "0x8E13649613B774Ab67D1C1eDfc22a2202270fD81"


# Create OCEAN object. ocean_lib knows where OCEAN is on all remote networks 
OCEAN = ocean.OCEAN_token
# Create Alice's wallet
from brownie.network import accounts
accounts.clear()

alice_private_key = os.getenv('REMOTE_TEST_PRIVATE_KEY1')
alice = accounts.add(alice_private_key)
assert alice.balance() > 0, "Alice needs MATIC"
assert OCEAN.balanceOf(alice) > 0, "Alice needs OCEAN"
# Publish Ocean asset

name = "ETH predictions " + str(time.time()) #time for unique name
(data_nft, datatoken, ddo) = ocean.assets.create_url_asset(name, url, {"from":alice}, wait_for_aqua=False)
metadata_state = 5
data_nft.setMetaDataState(metadata_state, {"from":alice})

# add to desight
print(f"New asset created, with did={ddo.did}, and datatoken.address={datatoken.address}")



# send to judge



from web3.main import Web3

datatoken.mint(to_address, Web3.toWei(10, "ether"), {"from": alice})