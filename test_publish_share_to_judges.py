# -*- coding: utf-8 -*-

# Imports
# Create Ocean instance
import os
from pathlib import Path
from dotenv import load_dotenv, find_dotenv

from eth_account import Account
from web3.logs import DISCARD
from ocean_lib.example_config import get_config_dict
from ocean_lib.ocean.ocean import Ocean
from ocean_lib.ocean import crypto


load_dotenv(find_dotenv())
config = get_config_dict("mumbai")
ocean = Ocean(config)
filename_pred = "data/pred_vals_test.csv"

def load_list(file_name: str) -> list:
    """Load from a file shaped: [1.2, 3.4, 5.6, ..]"""
    p = Path(file_name)
    s = p.read_text()
    list_ = eval(s)
    return list_

# def
judges_pubkey = '0xe9f670d726c5a943dc05cd7d04729e3261d41190fc8d01d2898550faf04dc5a7c08ab49446d7966aa804c8b91c0b72bf2d688b868ccedd2a8c6cf2f5c49987e1'
judges_address = '0xf0eFB20F715c436D8774BbA18621CcF28f975078'
# Load model predictions
pred_vals = load_list(filename_pred)
# Create OCEAN object. ocean_lib knows where OCEAN is on all remote networks
OCEAN = ocean.OCEAN_token

# Create Alice's wallet


alice_private_key = os.getenv('REMOTE_TEST_PRIVATE_KEY1')
alice = Account.from_key(private_key=alice_private_key)
assert ocean.wallet_balance(alice) > 0, "Alice needs MATIC"
assert OCEAN.balanceOf(alice) > 0, "Alice needs OCEAN"

# Create data NFT
data_nft = ocean.data_nft_factory.create({"from": alice}, 'Data NFT 1', 'DN1')
print(f"Created data NFT with address={data_nft.address}")

# Encrypt predictions with judges' public key, so competitors can't see.
# NOTE: public key is *not* the same thing as address. Using address will not work.

pred_vals_str = str(pred_vals)
pred_vals_str_enc = crypto.asym_encrypt(pred_vals_str, judges_pubkey)

# Store predictions to data NFT, on-chain
data_nft.set_data("predictions", pred_vals_str_enc, {"from": alice})

# Transfer the data NFT to judges, for prediction tamper-resistance
token_id = 1
tx = data_nft.safeTransferFrom(alice.address, judges_address, token_id, {"from": alice})

# Ensure the transfer was successful
assert tx.status == 1

# and then from the individual event you can look at the event.args, e.g.
events = data_nft.contract.events.Transfer().process_receipt(
    tx,
    errors=DISCARD,
)
assert events[0].args.to.lower() == judges_address.lower()
#to_transact = f"0x{tx.logs[5-2].topics[2].hex()[-40:]}".lower()
#assert to_transact == judges_address.lower()

# Print txid, as we'll use it in the next step
print(f"txid from transferring the nft: {tx.transactionHash.hex()}")
print(f"txid URL: https://mumbai.polygonscan.com/tx/{tx.transactionHash.hex()}")