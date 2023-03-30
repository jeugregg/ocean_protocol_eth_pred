# -*- coding: utf-8 -*-

# Imports
from dotenv import load_dotenv, find_dotenv
from ocean_lib.web3_internal.utils import connect_to_network
from ocean_lib.example_config import get_config_dict
from ocean_lib.ocean.ocean import Ocean
from ocean_lib.ocean import crypto
from helpers.ocean_helpers import create_alice_wallet
from helpers.ocean_helpers import load_list, save_list

# definitions
load_dotenv(find_dotenv())
filename_pred = "data/pred_vals_test.csv"
# save list
save_list([12.1, 13.3, 14.2], filename_pred)
# Load model predictions
pred_vals = load_list(filename_pred)

# Create Ocean instance
connect_to_network("polygon-test") # mumbai is "polygon-test"
config = get_config_dict("polygon-test")
ocean = Ocean(config)

# my wallet
alice = create_alice_wallet(ocean) #you're Alice

# Create data NFT
data_nft = ocean.data_nft_factory.create({"from": alice}, 'Data NFT 1', 'DN1')
print(f"Created data NFT with address={data_nft.address}")

# Encrypt predictions with judges' public key, so competitors can't see
judges_pubkey = '0xe9f670d726c5a943dc05cd7d04729e3261d41190fc8d01d2898550faf04dc5a7c08ab49446d7966aa804c8b91c0b72bf2d688b868ccedd2a8c6cf2f5c49987e1'
pred_vals_str = str(pred_vals)
pred_vals_str_enc = crypto.asym_encrypt(pred_vals_str, judges_pubkey)

# Store predictions to data NFT, on-chain
data_nft.set_data("predictions", pred_vals_str_enc, {"from": alice})

# Transfer the data NFT to judges, for prediction tamper-resistance
judges_address = '0xf0eFB20F715c436D8774BbA18621CcF28f975078'
token_id = 1
tx = data_nft.safeTransferFrom(alice.address, judges_address, token_id, {"from": alice})

# Ensure the transfer was successful
assert tx.events['Transfer']['to'].lower() == judges_address.lower()

# Print txid, as we'll use it in the next step
print(f"txid from transferring the nft: {tx.txid}")
