from time import time
import secrets

from cryptography.hazmat.primitives import serialization
import jwt

from vcc import settings, VCCError


secret = secrets.token_hex(8)  # secret key that will be used by VCC to create JWT token


# Make signature and encode using ssh private key
def make(group_id, data={}, exp=0):
    global secret

    if not hasattr(settings.Signatures, group_id):
        raise VCCError(f'{group_id} not in configuration file')

    code, uid = getattr(settings.Signatures, group_id)
    data = dict(**data, **{'code': code, 'group': group_id, 'secret': secret})
    if exp > 0:
        data['exp'] = time() + exp
    # use ssh private key to encode Jason Web Token
    try:  # Decode file as not PEM format
        key = serialization.load_ssh_private_key(open(settings.KEY, 'r').read().encode(), password=b'')
    except ValueError:  # It looks like file is in PEM format
        key = open(settings.KEY, 'r').read()
    return {'token': jwt.encode(payload=data, key=key, algorithm='RS256', headers={'uid': uid})}


# Validate signature of information received by VCC
def validate(rsp):
    global secret
    token = rsp.headers.get('token')
    if not token:
        raise VCCError('Invalid signature [no token]')
    headers = jwt.get_unverified_header(token)
    if not headers:
        raise VCCError('Invalid signature [no header in token]')
    group_id = headers.get('group')
    if not group_id or not hasattr(settings.Signatures, group_id):
        raise VCCError('Invalid signature [invalid group]')
    try:
        info = jwt.decode(token, secret, algorithms=headers['alg'])
        _, uid = getattr(settings.Signatures, group_id)
        if info.get('uid') != uid:
            raise VCCError('Invalid signature [bad UID]')
        return info
    except (jwt.exceptions.ExpiredSignatureError, jwt.exceptions.InvalidSignatureError) as exc:
        raise VCCError(str(exc))


