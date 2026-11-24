"""Herramienta del técnico (se usa en TU PC, nunca en la del cliente).

  python firmar.py claves                      crea tu clave privada (una sola vez)
  python firmar.py configurar                  graba clave pública + clave de técnico en el actualizador
  python firmar.py empaquetar setup.exe 0.6.0  crea el .gipupdate firmado (y el índice para internet)

La clave privada queda cifrada con una frase de paso. Si la perdés no podés publicar
más actualizaciones para los actualizadores ya instalados; si te la roban, pueden
publicar actualizaciones falsas: guardala fuera del repositorio y con copia offline.
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

DEFAULT_KEY = Path.home() / 'gip-firma' / 'clave-privada.pem'
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
    data = path.read_bytes()
    key = serialization.load_pem_private_key(data, getpass.getpass('Frase de la clave privada: ').encode())
    if not isinstance(key, Ed25519PrivateKey):
        sys.exit('La clave no es Ed25519.')
    return key


def public_b64(key: Ed25519PrivateKey) -> str:
    raw = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return base64.b64encode(raw).decode()


def cmd_claves(args: argparse.Namespace) -> None:
    path = Path(args.salida)
    if path.exists():
        sys.exit(f'Ya existe {path}. No se sobrescribe una clave de firma.')
    phrase = secret('Frase para proteger la clave privada (mín. 16): ', 16)
    key = Ed25519PrivateKey.generate()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                       serialization.BestAvailableEncryption(phrase.encode())))
    print('Clave privada guardada en:', path)
    print('Clave pública:', public_b64(key))
    print('Hacé una copia de la clave privada en un pendrive guardado aparte.')


def cmd_configurar(args: argparse.Namespace) -> None:
    key = load_key(Path(args.clave))
    technician = secret('Clave de técnico para el botón Actualizar (mín. 16): ', 16)
    TRUST.write_text(json.dumps({'public_key': public_b64(key), 'technician_hash': hash_technician(technician),
                                 'index_url': args.indice}, indent=2) + '\n', encoding='utf-8')
    print('Actualizador configurado en', TRUST)


def cmd_empaquetar(args: argparse.Namespace) -> None:
    installer = Path(args.instalador)
    key = load_key(Path(args.clave))
    output = Path(args.salida or f'GestionInteligentePOS-{args.version}.gipupdate')
    package.create_package(installer, args.version, key, output, args.notas)
    print('Paquete firmado:', output)
    if args.url:
        manifest = package.parse_manifest(package.build_manifest(installer, args.version, args.notas))
        index = package.build_index(manifest, args.url, package.file_sha256(output))
        Path('latest.json').write_bytes(index)
        Path('latest.json.sig').write_bytes(package.sign(key, index))
        print('Índice firmado: latest.json y latest.json.sig (subilos al Release junto al paquete)')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(required=True)
    p = sub.add_parser('claves')
    p.add_argument('--salida', default=str(DEFAULT_KEY))
    p.set_defaults(run=cmd_claves)
    p = sub.add_parser('configurar')
    p.add_argument('--clave', default=str(DEFAULT_KEY))
    p.add_argument('--indice', default=DEFAULT_INDEX)
    p.set_defaults(run=cmd_configurar)
    p = sub.add_parser('empaquetar')
    p.add_argument('instalador')
    p.add_argument('version')
    p.add_argument('--clave', default=str(DEFAULT_KEY))
    p.add_argument('--notas', default='')
    p.add_argument('--salida')
    p.add_argument('--url', help='URL https donde vas a publicar el .gipupdate (genera latest.json firmado)')
    p.set_defaults(run=cmd_empaquetar)
    args = parser.parse_args()
    args.run(args)


if __name__ == '__main__':
    main()
