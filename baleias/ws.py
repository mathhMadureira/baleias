"""Cliente WebSocket mínimo (RFC 6455) só com a biblioteca padrão: o projeto não tem dependências externas."""
import base64
import hashlib
import json
import os
import socket
import ssl
import struct
import urllib.parse

GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
MAX_QUADRO = 16 * 1024 * 1024


class Fechado(ConnectionError):
    pass


class WS:
    def __init__(self, sock):
        self.s = sock
        self._buf = b""

    @classmethod
    def conectar(cls, url, timeout=30):
        u = urllib.parse.urlsplit(url)
        porta = u.port or (443 if u.scheme == "wss" else 80)
        bruto = socket.create_connection((u.hostname, porta), timeout=timeout)
        s = ssl.create_default_context().wrap_socket(bruto, server_hostname=u.hostname) if u.scheme == "wss" else bruto
        caminho = (u.path or "/") + (f"?{u.query}" if u.query else "")
        chave = base64.b64encode(os.urandom(16)).decode()
        s.sendall((f"GET {caminho} HTTP/1.1\r\nHost: {u.hostname}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                   f"Sec-WebSocket-Key: {chave}\r\nSec-WebSocket-Version: 13\r\nUser-Agent: baleias\r\n\r\n").encode())
        ws = cls(s)
        cabecalho = ws._ate(b"\r\n\r\n").decode("latin-1")
        if " 101 " not in cabecalho.split("\r\n")[0]:
            raise ConnectionError(f"handshake recusado: {cabecalho.splitlines()[0][:80]}")
        esperado = base64.b64encode(hashlib.sha1((chave + GUID).encode()).digest()).decode()
        if esperado not in cabecalho:
            raise ConnectionError("handshake inválido (Sec-WebSocket-Accept)")
        return ws

    def _ler(self, n):
        while len(self._buf) < n:
            parte = self.s.recv(65536)
            if not parte:
                raise Fechado("conexão fechada pelo servidor")
            self._buf += parte
        dados, self._buf = self._buf[:n], self._buf[n:]
        return dados

    def _ate(self, fim):
        while fim not in self._buf:
            parte = self.s.recv(4096)
            if not parte:
                raise Fechado("conexão fechada durante o handshake")
            self._buf += parte
        i = self._buf.index(fim) + len(fim)
        dados, self._buf = self._buf[:i], self._buf[i:]
        return dados

    def enviar(self, texto, opcode=1):
        dados = texto.encode() if isinstance(texto, str) else texto
        mascara = os.urandom(4)
        n = len(dados)
        if n < 126:
            cab = struct.pack("!BB", 0x80 | opcode, 0x80 | n)
        elif n < 65536:
            cab = struct.pack("!BBH", 0x80 | opcode, 0x80 | 126, n)
        else:
            cab = struct.pack("!BBQ", 0x80 | opcode, 0x80 | 127, n)
        self.s.sendall(cab + mascara + bytes(b ^ mascara[i % 4] for i, b in enumerate(dados)))

    def enviar_json(self, x):
        self.enviar(json.dumps(x))

    def receber(self):
        """Próxima mensagem de texto ou binária; responde pings e junta fragmentos sozinho."""
        partes, tipo = [], None
        while True:
            b0, b1 = self._ler(2)
            fim, opcode = b0 & 0x80, b0 & 0x0F
            n = b1 & 0x7F
            if n == 126:
                n = struct.unpack("!H", self._ler(2))[0]
            elif n == 127:
                n = struct.unpack("!Q", self._ler(8))[0]
            if n > MAX_QUADRO:
                raise ConnectionError("quadro grande demais")
            mascara = self._ler(4) if b1 & 0x80 else None
            dados = self._ler(n)
            if mascara:
                dados = bytes(b ^ mascara[i % 4] for i, b in enumerate(dados))
            if opcode == 9:
                self.enviar(dados, opcode=10)
                if getattr(self, "ao_ping", None):
                    self.ao_ping()
                continue
            if opcode == 10:
                continue
            if opcode == 8:
                raise Fechado("servidor encerrou a conexão")
            if opcode in (1, 2):
                tipo = opcode
            partes.append(dados)
            if fim:
                corpo = b"".join(partes)
                return corpo.decode() if tipo == 1 else corpo

    def fechar(self):
        try:
            self.enviar(b"", opcode=8)
        except OSError:
            pass
        self.s.close()
