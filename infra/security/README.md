# Baseline de servidor Nexova

El baseline declarativo deja acceso público sólo por SSH `22/tcp` y HTTPS
`443/tcp`. Las aplicaciones y almacenes se enlazan a loopback en Compose; el
reverse proxy TLS es el único consumidor externo de los frontends.

`apply_server_hardening.sh` no cambia nada por defecto. `--check` inspecciona el
host. `--apply` exige root, una clave pública existente y confirmación explícita;
crea `nexova-deploy`, instala permisos y valida SSH/nftables antes de recargar.

```bash
sudo scripts/security/apply_server_hardening.sh --check
sudo scripts/security/apply_server_hardening.sh --apply /ruta/absoluta/id_ed25519.pub I_UNDERSTAND
sudo scripts/security/apply_server_hardening.sh --check
```

La aplicación debe hacerse desde consola del proveedor o con una segunda sesión
SSH abierta para poder revertir. El script guarda copias fechadas de las
configuraciones existentes. No se ha ejecutado contra el Mac de desarrollo ni
contra un servidor desconocido.

Permisos resultantes:

| Ruta | Propietario | Modo | Uso |
| --- | --- | --- | --- |
| `/opt/nexova/app` | `root:nexova-deploy` | `0750` | código inmutable para operaciones |
| `/var/log/nexova` | `nexova-deploy:nexova-deploy` | `0750` | logs del servicio |
| `/etc/nexova` | `root:nexova-deploy` | `0750` | configuración |
| `/etc/nexova/runtime.env` | `root:nexova-deploy` | `0640` | secretos inyectados por el vault |

Rollback manual: restaurar los backups indicados por el script desde consola,
validar con `sshd -t`/`nft -c` y recargar los servicios.
