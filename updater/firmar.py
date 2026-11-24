"""Herramienta del técnico (se usa en TU PC, nunca en la del cliente).

  python firmar.py claves --nombre principal        crea una clave privada + su .pub
  python firmar.py claves --nombre respaldo --salida E:\\gip-firma\\respaldo.pem   (pendrive offline)
  python firmar.py configurar --publica principal.pub --publica respaldo.pub
  python firmar.py empaquetar setup.exe 0.6.0 [--url https://.../x.gipupdate]

Anillo de claves: el actualizador acepta paquetes firmados por cualquiera de las claves
públicas configuradas. Con una clave de RESPALDO guardada offline podés seguir publicando
si perdés o te roban la principal (ver updater/README.md, "Claves de firma").
Este script nunca imprime ni sube la clave privada.
"""
from __future__ import annotations

import argparse
import base64
import getpass
import json
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

sys.path.insert(0, str(Path(__file__).parent))
from gip_updater import package
from gip_updater.auth import hash_technician
from gip_updater.storage import file_sha256

DEFAULT_DIR = Path.home() / 'gip-firma'
TRUST = Path(__file__).parent / 'gip_updater' / 'trust.json'
DEFAULT_INDEX = 'https://github.com/NicolasAriel32/gestion-inteligente-pos/releases/latest/download/latest.json'


def secret(prompt: str, minimum: int) -> str:
    first = getpass.getpass(prompt)
    if len(first) < minimum:
        sys.exit(f'Debe tener al menos {minimum} caracteres.')
    if getpass.getpass('Repetila: ') != first:
        sys.exit('No coinciden.')
    return first


def load_key(path: Path) -> Ed25519PrivateKey:
    key = serialization.load_pem_private_key(path.read_bytes(), getpass.getpass(f'Frase de {path.name}: ').encode())
    if not isinstance(key, Ed25519PrivateKey):
        sys.exit('La clave no es Ed25519.')
    return key


def public_b64(key) -> str:
    return base64.b64encode(package.raw_public(key)).decode()


def cmd_claves(args: argparse.Namespace) -> None:
    path = Path(args.salida) if args.salida else DEFAULT_DIR / f'{args.nombre}.pem'
    if path.exists():
        sys.exit(f'Ya existe {path}. No se sobrescribe una clave de firma.')
    phrase = secret(f'Frase para proteger la clave "{args.nombre}" (mín. 16): ', 16)
    key = Ed25519PrivateKey.generate()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                       serialization.BestAvailableEncryption(phrase.encode())))
    pub = path.with_suffix('.pub')
    pub.write_text(public_b64(key.public_key()) + '\n', encoding='ascii')
    print(f'Clave privada: {path}\nClave pública: {pub} (id {package.key_id(key.public_key())})')


def cmd_configurar(args: argparse.Namespace) -> None:
    publics = [Path(p).read_text(encoding='ascii').strip() for p in args.publica]
    keyring = package.Keyring.from_trust({'public_keys': publics})  # valida cada una
    if len(keyring.keys) != len(publics):
        sys.exit('Hay claves públicas repetidas.')
    technician = secret('Clave de técnico para el botón Actualizar (mín. 16): ', 16)
    TRUST.write_text(json.dumps({'public_keys': publics, 'technician_hash': hash_technician(technician),
                                 'index_url': args.indice}, indent=2) + '\n', encoding='utf-8')
    print('Actualizador configurado con claves:', ', '.join(keyring.keys), '→', TRUST)


def cmd_empaquetar(args: argparse.Namespace) -> None:
    installer = Path(args.instalador)
    key = load_key(Path(args.clave))
    output = Path(args.salida or f'GestionInteligentePOS-{args.version}.gipupdate')
    package.create_package(installer, args.version, key, output, args.notas)
    print('Paquete firmado:', output, 'con clave', package.key_id(key.public_key()))
    if args.url:
        manifest = package.parse_manifest(package.build_manifest(installer, args.version, key.public_key(), args.notas))
        index = package.build_index(manifest, args.url, file_sha256(output))
        Path('latest.json').write_bytes(index)
        Path('latest.json.sig').write_bytes(package.sign(key, index))
        print('Índice firmado: latest.json y latest.json.sig (subilos al Release junto al paquete)')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(required=True)
    p = sub.add_parser('claves')
    p.add_argument('--nombre', default='principal')
    p.add_argument('--salida')
    p.set_defaults(run=cmd_claves)
    p = sub.add_parser('configurar')
    p.add_argument('--publica', action='append', required=True, help='Archivo .pub; repetir para la de respaldo')
    p.add_argument('--indice', default=DEFAULT_INDEX)
    p.set_defaults(run=cmd_configurar)
    p = sub.add_parser('empaquetar')
    p.add_argument('instalador')
    p.add_argument('version')
    p.add_argument('--clave', default=str(DEFAULT_DIR / 'principal.pem'))
    p.add_argument('--notas', default='')
    p.add_argument('--salida')
    p.add_argument('--url', help='URL https donde vas a publicar el .gipupdate (genera latest.json firmado)')
    p.set_defaults(run=cmd_empaquetar)
    args = parser.parse_args()
    args.run(args)


if __name__ == '__main__':
    main()
