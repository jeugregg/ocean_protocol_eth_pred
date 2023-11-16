# Imports
import os
from pathlib import Path
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

from web3.logs import DISCARD
from eth_account import Account
from ocean_lib.ocean import crypto
#from ocean_lib.web3_internal.utils import connect_to_network
from ocean_lib.example_config import get_config_dict
from ocean_lib.ocean.ocean import Ocean
#from helpers.ocean_helpers import create_alice_wallet
#from helpers.ocean_helpers import load_list

def load_list(file_name: str) -> list:
    """Load from a file shaped: [1.2, 3.4, 5.6, ..]"""
    p = Path(file_name)
    s = p.read_text()
    list_ = eval(s)
    return list_
# Definitions
judges_address = '0xA54ABd42b11B7C97538CAD7C6A2820419ddF703E'
judges_pubkey = '0x3d87bf8bde8c093a16ca5441b5a1053d34a28aca75dc4afffb7a2a513f2a16d2ac41bac68d8fc53058ed4846de25064098bbfaf0e1a5979aeb98028ce69fab6a'
filename_pred = "data/pred_vals.csv"
pred_vals = load_list(filename_pred)

# Create Ocean instance
#connect_to_network("polygon-test") # mumbai is "polygon-test"
#config = get_config_dict("polygon-test")
#ocean = Ocean(config)
config = get_config_dict("mumbai")
ocean = Ocean(config)
# Create OCEAN object. ocean_lib knows where OCEAN is on all remote networks
OCEAN = ocean.OCEAN_token
# my wallet
alice_private_key = os.getenv('REMOTE_TEST_PRIVATE_KEY1')
alice = Account.from_key(private_key=alice_private_key)
assert ocean.wallet_balance(alice) > 0, "Alice needs MATIC"
assert OCEAN.balanceOf(alice) > 0, "Alice needs OCEAN"

# Create data NFT
data_nft = ocean.data_nft_factory.create({"from": alice}, 'Data NFT 1', 'DN1')
print(f"Created data NFT with address={data_nft.address}")

# Encrypt predictions with judges' public key, so competitors can't see
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
