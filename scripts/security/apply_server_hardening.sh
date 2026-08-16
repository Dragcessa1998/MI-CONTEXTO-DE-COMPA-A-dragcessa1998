#!/bin/sh
set -eu

deploy_user="nexova-deploy"
app_dir="/opt/nexova/app"
log_dir="/var/log/nexova"
config_dir="/etc/nexova"
ssh_target="/etc/ssh/sshd_config.d/99-nexova-hardening.conf"
nft_target="/etc/nftables.conf"
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo_root=$(CDPATH= cd -- "$script_dir/../.." && pwd)
ssh_source="$repo_root/infra/security/sshd_config.d/99-nexova-hardening.conf"
nft_source="$repo_root/infra/security/nftables.conf"

check_host() {
  id "$deploy_user"
  test "$(stat -c '%U:%G:%a' "$app_dir")" = "root:$deploy_user:750"
  test "$(stat -c '%U:%G:%a' "$log_dir")" = "$deploy_user:$deploy_user:750"
  test "$(stat -c '%U:%G:%a' "$config_dir")" = "root:$deploy_user:750"
  test "$(stat -c '%U:%G:%a' "$config_dir/runtime.env")" = "root:$deploy_user:640"
  sshd -t
  sshd -T -C user="$deploy_user",host=localhost,addr=127.0.0.1 | grep -q '^permitrootlogin no$'
  sshd -T -C user="$deploy_user",host=localhost,addr=127.0.0.1 | grep -q '^passwordauthentication no$'
  nft -c -f "$nft_target"
  nft list ruleset | grep -q 'tcp dport { 22, 443 }'
  echo "OK: usuario, SSH, permisos y firewall Nexova verificados"
}

if [ "${1:-}" = "--check" ]; then
  check_host
  exit 0
fi

if [ "${1:-}" != "--apply" ] || [ "$#" -ne 3 ] || [ "$3" != "I_UNDERSTAND" ]; then
  echo "Uso: $0 --check | --apply /ruta/absoluta/clave.pub I_UNDERSTAND" >&2
  exit 2
fi

public_key_file=$2
case "$public_key_file" in
  /*) ;;
  *) echo "La clave pública debe usar una ruta absoluta" >&2; exit 2 ;;
esac
if [ "$(id -u)" -ne 0 ]; then
  echo "--apply requiere root" >&2
  exit 2
fi
test -f "$public_key_file"
grep -Eq '^(ssh-ed25519|ecdsa-sha2-nistp256|sk-ssh-ed25519@openssh.com) ' "$public_key_file"
test -f "$ssh_source"
test -f "$nft_source"
command -v useradd >/dev/null
command -v sshd >/dev/null
command -v nft >/dev/null

timestamp=$(date -u +%Y%m%dT%H%M%SZ)
if ! id "$deploy_user" >/dev/null 2>&1; then
  useradd --create-home --home-dir "/home/$deploy_user" --shell /bin/bash "$deploy_user"
fi
install -d -o "$deploy_user" -g "$deploy_user" -m 0700 "/home/$deploy_user/.ssh"
install -o "$deploy_user" -g "$deploy_user" -m 0600 "$public_key_file" "/home/$deploy_user/.ssh/authorized_keys"
install -d -o root -g "$deploy_user" -m 0750 "$app_dir" "$config_dir"
install -d -o "$deploy_user" -g "$deploy_user" -m 0750 "$log_dir"
if [ ! -f "$config_dir/runtime.env" ]; then
  install -o root -g "$deploy_user" -m 0640 /dev/null "$config_dir/runtime.env"
else
  chown root:"$deploy_user" "$config_dir/runtime.env"
  chmod 0640 "$config_dir/runtime.env"
fi

test -d /etc/ssh/sshd_config.d
if [ -f "$ssh_target" ]; then cp -p "$ssh_target" "$ssh_target.backup-$timestamp"; fi
install -o root -g root -m 0644 "$ssh_source" "$ssh_target"
sshd -t

if [ -f "$nft_target" ]; then cp -p "$nft_target" "$nft_target.backup-$timestamp"; fi
install -o root -g root -m 0600 "$nft_source" "$nft_target"
nft -c -f "$nft_target"
nft -f "$nft_target"

if command -v systemctl >/dev/null; then
  systemctl reload ssh || systemctl reload sshd
  systemctl enable --now nftables
fi

check_host
echo "Backups identificados con sufijo: backup-$timestamp"
