#!/usr/bin/env python3
"""Sert le dossier du projet avec les en-tetes COOP/COEP requis par
ffmpeg.wasm (SharedArrayBuffer est completement desactive par Chrome sans
ces deux en-tetes, meme pour le coeur ffmpeg non multi-thread) — le
serveur generique `python -m http.server` (utilise pour l'app elle-meme)
ne les envoie pas, d'ou un serveur dedie pour l'editeur de Reels."""
import http.server
import sys
from pathlib import Path

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8936


class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cross-Origin-Opener-Policy', 'same-origin')
        self.send_header('Cross-Origin-Embedder-Policy', 'require-corp')
        super().end_headers()


if __name__ == '__main__':
    import os
    os.chdir(Path(__file__).parent.parent.parent)  # racine du projet
    http.server.test(HandlerClass=Handler, port=PORT)
