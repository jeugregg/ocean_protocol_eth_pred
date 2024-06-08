from ocean_lib.ocean import crypto

from base64 import b64encode
from hashlib import sha256

def calc_symkey(base_str: str) -> str:
    """Compute a symmetric private key that's a function of the base_str"""
    base_b = base_str.encode("utf-8")  # bytes
    hash_b = sha256(base_b).hexdigest()
    symkey_b = b64encode(str(hash_b).encode("ascii"))[:43] + b"="  # bytes
    symkey = symkey_b.decode("ascii")
    return symkey

print("\n\nTEST ENCRYPTIONS ASYM & SIGN & SYM:")
# Test asymmetric encryption : 
# (utilisé par exemple pour envoyer resultat prediction ETH price to judges)
#0x6b57a5dffe2954564f00138ee8bba060ceb9ef8c5c0b903f5aff1d4c9cde1062
private_key = "0x6b57a5dffe2954564f00138ee8bba060ceb9ef8c5c0b903f5aff1d4c9cde1062"

public_key = crypto.calc_pubkey(private_key)

message = "HELLO TEST 1!"
message_enc = crypto.asym_encrypt(message, public_key)
message_dec = crypto.asym_decrypt(message_enc, private_key)
print("\nasymetric encryption : ")
print("public_key: " + public_key)
print("message: " + message)
print("message_enc: " + message_enc)
print("message_dec: " + message_dec)

# try to decrypt with wrong private key
print("\ntry to decrypt with wrong private key: ")
wrong_private_key = "0x2b57a5dffe2954564f00138ee8bba060ceb9ef8c5c0b903f5aff1d4c9cde1063"
try:
    message_dec = crypto.asym_decrypt(message_enc, wrong_private_key)
    print("message_dec: " + message_dec)
except Exception as e:
    print(e)

# Test de signature :
# pour signer un message : on chiffre le hash du message avec la clé privée
from web3 import Web3
from eth_account.messages import encode_defunct

# Initialisez Web3 avec un nœud Ethereum (par exemple, Infura)
w3 = Web3(Web3.HTTPProvider('https://mainnet.infura.io/v3/YOUR_INFURA_PROJECT_ID'))
# Remplacez 'YOUR_INFURA_PROJECT_ID' par votre propre ID de projet Infura

def sign_message(private_key, message):
    # Encodez le message
    message_to_sign = encode_defunct(text=message)

    # Signez le message avec la clé privée
    signed_message = w3.eth.account.sign_message(message_to_sign, private_key=private_key)

    # Renvoyez la signature sous forme de chaîne hexadécimale
    return signed_message.signature.hex()

# Exemple d'utilisation
print("\nSigner un message : ")
message_to_sign = "Hello, this is my signed message!"

signature = sign_message(private_key, message_to_sign)
print(f"Signature du message : {signature}")


# Symetric encryption :
# on derive/calcul une clé symetrique à partir de la clé privée 
# fonction à sens unique (hash)
# mais on peut dériver à partir de n'importe quelle chaine de caractere
print("\nSymetric encryption : ")
sym_key = calc_symkey(private_key)
print("sym_key: " + sym_key)
message_enc = crypto.sym_encrypt(message, sym_key)
print("message_enc: " + message_enc)
message_dec = crypto.sym_decrypt(message_enc, sym_key)
print("message_dec: " + message_dec)

# try to decrypt with wrong sym_key
print("\ntry to decrypt with wrong sym_key: ")
print("private_key      : " + private_key)
print("wrong_private_key: " + wrong_private_key)
wrong_sym_key = calc_symkey(wrong_private_key)
print("sym_key      : " + sym_key)
print("wrong_sym_key: " + wrong_sym_key)
assert wrong_sym_key != sym_key, "NOK : wrong_sym_key is the same as sym_key"
try:
    message_dec = crypto.sym_decrypt(message_enc, wrong_sym_key)
    print("message_dec: " + message_dec)
except Exception as e:
    # A ValueError is raised if the message cannot be decrypted with the key
    print("OK : message cannot be decrypted with the wrong sym key : ")
    print(type(e))

print("END")
"""base_b = private_key.encode("utf-8")  # bytes
hash_b = sha256(base_b).hexdigest()
symkey_b = b64encode(str(hash_b).encode("ascii"))[:43] + b"="  # bytes
symkey = symkey_b.decode("ascii")

base_b1 = wrong_private_key.encode("utf-8")  # bytes
hash_b1 = sha256(base_b1).hexdigest()
symkey_b1 = b64encode(str(hash_b1).encode("ascii"))[:43] + b"="  # bytes
symkey1 = symkey_b1.decode("ascii")"""