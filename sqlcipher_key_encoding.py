import base64

def encode_sqlcipher_key_base64(key: str) -> str:
    """Encode the key using Base64."""
    return base64.b64encode(key.encode()).decode()

def decode_sqlcipher_key_base64(encoded_key: str) -> str:
    """Decode the Base64-encoded key."""
    return base64.b64decode(encoded_key.encode()).decode()

def encode_sqlcipher_key_hex(key: str) -> str:
    """Encode the key using hexadecimal."""
    return key.encode().hex()

def decode_sqlcipher_key_hex(encoded_key: str) -> str:
    """Decode the hex-encoded key."""
    return bytes.fromhex(encoded_key).decode()

def main():
    original_key = input("Enter your SQLCIPHER_KEY: ")

    # Choose encoding type: "base64" or "hex"
    encoding_type = input("Choose encoding type (base64/hex): ").strip().lower()

    if encoding_type == "base64":
        encoded = encode_sqlcipher_key_base64(original_key)
        print(f"Base64 encoded key: {encoded}")
        decoded = decode_sqlcipher_key_base64(encoded)
        print(f"Decoded key: {decoded}")
    elif encoding_type == "hex":
        encoded = encode_sqlcipher_key_hex(original_key)
        print(f"Hex encoded key: {encoded}")
        decoded = decode_sqlcipher_key_hex(encoded)
        print(f"Decoded key: {decoded}")
    else:
        print("Unsupported encoding type. Use 'base64' or 'hex'.")

if __name__ == "__main__":
    main()