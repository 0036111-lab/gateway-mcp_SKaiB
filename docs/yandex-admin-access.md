# Yandex VM administration through Düsseldorf

The production GatewayMCP VM is not administered through its public SSH address.
Use Yandex OS Login with a short-lived certificate and route SSH through the
Düsseldorf WireGuard host.

## Route

`administrator -> 206.189.53.60 (Düsseldorf) -> 10.77.0.1 (Yandex VM)`

The Düsseldorf host uses the local key `~/.ssh/yandex_gateway`. Never commit
that key or an exported OS Login certificate.

The local SSH aliases are canonical: `skaib-dusseldorf` is the jump host and
`skaib-yandex-gateway` is the production VM. Do not administer the VM through
its public IP.

## Connect

Export a fresh certificate into a private temporary directory. The command
prints the generated key paths; use the path without the `-cert.pub` suffix as
`YC_OSLOGIN_KEY`:

```sh
YC_CERT_DIR="$(mktemp -d)"
chmod 700 "$YC_CERT_DIR"
yc compute ssh certificate export --directory "$YC_CERT_DIR"

ssh \
  -i "$YC_OSLOGIN_KEY" \
  skaib-yandex-gateway
```

The production Compose project is `/home/anas-pyshkina/gateway-mcp`. After VM
maintenance, verify it with `sudo docker compose ps`; all three services must
be running, and PostgreSQL and Gateway must be healthy.

The Compose services use `restart: unless-stopped`, so ordinary VM reboots do
not require manual startup.
