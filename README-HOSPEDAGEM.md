# Nexora Academy Downloader 3.0

Aplicação Flask para capturar sites e gerar um arquivo ZIP para uso offline. Esta pasta contém o código da versão 3.0, a interface futurista laranja da Nexora Academy, progresso da captura, cancelamento cooperativo, histórico local e validação contra endereços de rede interna.

## Opção recomendada: Docker

O arquivo `Dockerfile` instala o Python, as dependências, o Chromium do Playwright e inicia a aplicação com Gunicorn.

```bash
docker build -t nexora-academy-downloader .
docker run --rm -p 5001:5001 -e PORT=5001 nexora-academy-downloader
```

Depois, abra `http://localhost:5001`.

Em plataformas que detectam Docker automaticamente, basta enviar esta pasta como repositório ou projeto. A porta deve ser obtida da variável de ambiente `PORT`; o contêiner já está configurado para utilizá-la.

## Hospedagem sem Docker

Use Python 3.12 ou superior:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install --with-deps chromium
gunicorn --bind 0.0.0.0:${PORT:-5001} --workers 1 --threads 8 --timeout 1800 app:app
```

É importante manter **um único worker** porque as sessões de captura ficam em memória durante a execução. A aplicação precisa de um ambiente que permita executar Chromium em modo headless.

## Arquivos principais

| Arquivo | Função |
|---|---|
| `app.py` | Servidor Flask, sessões, streaming de logs, cancelamento, segurança e download do ZIP. |
| `grabber.py` | Captura do site com Playwright, coleta de recursos e reescrita para uso offline. |
| `templates/index.html` | Interface Nexora Academy Downloader 3.0. |
| `requirements.txt` | Dependências Python. |
| `Dockerfile` | Imagem pronta para hospedagem com Chromium. |

## Observações de produção

A pasta `downloads/` é temporária e deve estar em armazenamento efêmero ou ser montada em um volume com limite de espaço. O código remove sessões expiradas automaticamente. Para uso público, recomenda-se colocar HTTPS e autenticação ou limitar o acesso por rede, além de configurar limites de CPU, memória e tamanho de captura na plataforma de hospedagem.

O endpoint de verificação é:

```text
GET /health
```

Uma resposta saudável possui `status: ok`.
