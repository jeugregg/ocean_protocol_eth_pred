# Imports
from ocean_lib.ocean import crypto
from ocean_lib.web3_internal.utils import connect_to_network
from ocean_lib.example_config import get_config_dict
from ocean_lib.ocean.ocean import Ocean
from ocean_lib.ocean import crypto
from helpers.ocean_helpers import create_alice_wallet
from helpers.ocean_helpers import load_list

# Definitions
judges_address = '0xA54ABd42b11B7C97538CAD7C6A2820419ddF703E'
judges_pubkey = '0x3d87bf8bde8c093a16ca5441b5a1053d34a28aca75dc4afffb7a2a513f2a16d2ac41bac68d8fc53058ed4846de25064098bbfaf0e1a5979aeb98028ce69fab6a'
filename_pred = "data/pred_vals.csv"
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
pred_vals_str = str(pred_vals)
pred_vals_str_enc = crypto.asym_encrypt(pred_vals_str, judges_pubkey)

# Store predictions to data NFT, on-chain
data_nft.set_data("predictions", pred_vals_str_enc, {"from": alice})

# Transfer the data NFT to judges, for prediction tamper-resistance
token_id = 1
tx = data_nft.safeTransferFrom(alice.address, judges_address, token_id, {"from": alice})

# Ensure the transfer was successful
assert tx.events['Transfer']['to'].lower() == judges_address.lower()

# Print txid, as we'll use it in the next step
print(f"txid from transferring the nft: {tx.txid}")