#!/usr/bin/env python
# Borrowed from https://gist.github.com/jtriley/7270594 and tweaked
# Tweaks include moving to argparse and dropping paramiko
import hashlib
import argparse
from Crypto.PublicKey import RSA


def insert_char_every_n_chars(string, char='\n', every=64):
    return char.join(
        string[i:i + every] for i in xrange(0, len(string), every))


def get_rsa_key(key_location=None, key_file_obj=None, passphrase=None):
    try:
        key_fobj = key_file_obj or open(key_location)
        key = RSA.importKey(key_fobj, passphrase=passphrase)
        return key
    except (ValueError):
        raise Exception(
            "Invalid RSA private key file or missing passphrase: %s" %
            key_location)


def get_private_rsa_fingerprint(key_location=None, key_file_obj=None,
                                passphrase=None):
    """
    Returns the fingerprint of a private RSA key as a 59-character string (40
    characters separated every 2 characters by a ':'). The fingerprint is
    computed using the SHA1 (hex) digest of the DER-encoded (pkcs8) RSA private
    key.
    """
    key = get_rsa_key(
        key_location=key_location,
        key_file_obj=key_file_obj,
        passphrase=passphrase
    )
    sha1digest = hashlib.sha1(key.exportKey('DER', pkcs=8)).hexdigest()
    fingerprint = insert_char_every_n_chars(sha1digest, ':', 2)
    return fingerprint


def get_public_rsa_fingerprint(key_location=None, key_file_obj=None,
                               passphrase=None):
    """
    Returns the fingerprint of the public portion of an RSA key as a
    47-character string (32 characters separated every 2 characters by a ':').
    The fingerprint is computed using the MD5 (hex) digest of the DER-encoded
    RSA public key.
    """
    privkey = get_rsa_key(
        key_location=key_location,
        key_file_obj=key_file_obj,
        passphrase=passphrase
    )
    pubkey = privkey.publickey()
    md5digest = hashlib.md5(pubkey.exportKey('DER')).hexdigest()
    fingerprint = insert_char_every_n_chars(md5digest, ':', 2)
    return fingerprint


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('path', help='Path to the RSA private key file')
    parser.add_argument('-p', '--public-only', action='store_true')
    parser.add_argument('-P', '--private-only', action='store_true')
    args = vars(parser.parse_args())

    if args['public_only']:
        print get_public_rsa_fingerprint(key_location=args['path'])
    elif args['opts.private_only']:
        print get_private_rsa_fingerprint(key_location=args['path'])
    else:
        print get_public_rsa_fingerprint(key_location=args['path'])
        print get_private_rsa_fingerprint(key_location=args['path'])


if __name__ == '__main__':
    main()

