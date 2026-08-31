# Deploy do Nexora Academy Downloader 3.0

Este pacote contém a versão completa do aplicativo, incluindo servidor Flask, captura com Playwright/Chromium, interface web, segurança básica contra SSRF, cancelamento, progresso e histórico local.

## Deploy recomendado com Docker

```bash
docker build -t nexora-downloader .
docker run --rm -p 5001:5001 -e PORT=5001 nexora-downloader
```

Acesse `http://localhost:5001`. Em serviços gerenciados, publique o repositório com o `Dockerfile` na raiz. A plataforma deve fornecer a variável `PORT`.

## Render

O arquivo `render.yaml` já define um serviço web Docker com health check em `/health`. No painel do Render, escolha **New → Blueprint** e aponte para o repositório. O plano precisa permitir execução de Chromium; o plano gratuito pode não ter memória suficiente para sites complexos.

## Railway

Crie um serviço a partir do repositório e selecione o Dockerfile. Gere um domínio público em **Settings → Networking**. Não é necessário definir `PORT` manualmente, pois o Railway fornece essa variável ao contêiner.

## Deploy com Python

```bash
chmod +x build.sh entrypoint.sh
./build.sh
./entrypoint.sh
```

O ambiente precisa ser Python 3.12+, possuir suporte a Chromium headless e manter um único worker do Gunicorn. As sessões são mantidas na memória do processo e os ZIPs são temporários.

## Teste de saúde

```bash
curl https://SEU-DOMINIO/health
```

Resposta esperada:

```json
{"active":0,"sessions":0,"status":"ok"}
```

## Estrutura do pacote

| Arquivo | Finalidade |
|---|---|
| `app.py` | API Flask, sessões, streaming SSE, segurança, cancelamento e download. |
| `grabber.py` | Motor Playwright de captura e transformação offline. |
| `templates/index.html` | Interface Nexora Academy Downloader 3.0. |
| `requirements.txt` | Dependências Python com versões fixadas. |
| `Dockerfile` | Imagem completa com Chromium e Gunicorn. |
| `Procfile` | Comando para plataformas baseadas em Procfile. |
| `entrypoint.sh` | Inicialização para hospedagem Python. |
| `build.sh` | Instalação das dependências e do Chromium. |
| `render.yaml` | Blueprint de deploy no Render. |
| `DEPLOY.md` | Guia rápido de publicação. |
| `RAILWAY_DEPLOY.md` | Passo a passo específico do Railway. |
| `README-HOSPEDAGEM.md` | Visão geral e observações de produção. |

## Limitações importantes

A aplicação gera arquivos temporários no disco e mantém o estado das capturas em memória. Use um único worker, limite recursos da plataforma e considere um volume persistente caso os ZIPs precisem sobreviver a reinícios. Para uso público, coloque HTTPS, autenticação ou controle de acesso na frente do serviço.
