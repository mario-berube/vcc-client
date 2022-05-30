from cryptography.hazmat.primitives import serialization
import jwt


def decode(token, key_file):
    headers = jwt.get_unverified_header(token)
    print(headers)
    secret = open(key_file, 'r').read()
    payload = jwt.decode(token, secret, algorithms=headers['alg'])
    print(payload)

# Make signature and encode using ssh private key
def make(uid, code, group_id, secret, timetag, key_file, data={}):
    data = dict(**data, **{'code': code, 'group': group_id, 'secret': secret, 'exp': timetag})
    print(data)
    #data = {'code': code, 'group': group_id, 'secret': secret}
    # use ssh private key to encode JWT
    try:
        key = serialization.load_ssh_private_key(open(key_file, 'r').read().encode(), password=b'')
    except ValueError:
        key=open(key_file, 'r').read()
    return jwt.encode(payload=data, key=key, algorithm='RS256', headers={'uid': uid})

group_id, code, uid = ["CC", "GSFC", "F9EDFF82-654E-480B-BA23-C4E12F274667",]
secret = '0bd7fc9c6b939427'
timetag = 1652386514.668731
key = "/Users/Mario/VLBI/keys/coord"

token = make(uid, code, group_id, secret, timetag, key, {})
print(len(token), '\n', token)


token = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsInVpZCI6IkY5RURGRjgyLTY1NEUtNDgwQi1CQTIzLUM0RTEyRjI3NDY2NyJ9.eyJjb2RlIjoiR1NGQyIsImdyb3VwIjoiQ0MiLCJzZWNyZXQiOiIwYmQ3ZmM5YzZiOTM5NDI3IiwidDEiOjE2NTIzODY1MTQuNjY4NzMxfQ.XT_ocx6DRrrKPUtal5V-2eSouPpn7QHcwMw1gtibsVVle1IpXzW6gZLOBsYnfk2XdMlOJ5TxB3-RC8qesqzhjeTshughF8FsD1rPkPS5HtS3cuRVYzzRcVZe1RHq1SGlYstTxpuymv0Q2DVDkWFTcKTy9lEwqrpErkf-ckMeKfspKcMPT1fJ30XTb_zx_tcxkQitvBFdnqHbnsFea3isDw-LvQHw_eztTvHHJwyICqIxxz_GxsR0_bfR0MZbe7705pLWOC6IRFbgY2QUi-bh2ihi12ZRghfi0pgyrlltcQh2HulHyxp_-NNsigdSIY3zX2v62Z6I-QrIUQwxyiUkbrtbtRJWuXALT0DKGp1p-RWJzPzbpDKIx6I2v0C9u5gKwjP7KbzCNnFE8MdJyrH2aOhMf1v_luLMelmNhX2v_ZkWJEmkX8YTr_HyO_6aTjIdSTxcB0PkTz4fu0zp7W6qALMLAfVVu2pGI_P7RJ7hBYnHCJGGbHiIhxGnzeIPGSc6oEuAzgmRtFGM7XbWXY8-2gWAtWJ0hc7uvq8E6tQMyaiXAzIy0i6jqGIjrPzLw2opm85ZXUSYk6sFSdfdQ09ZelptvyoJRKyJEKfPRrhxi1Ct2LL9-COI0vY96O6A_q3eUYm3V1zfrhGdVDgWfLExtWyUdDN-f5ttqNNnuUzf1IM"

decode(token, "/Users/Mario/VLBI/keys/testing.pub")