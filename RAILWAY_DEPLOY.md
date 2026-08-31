# Deploy no Railway

1. Crie um projeto novo em [railway.app](https://railway.app) e escolha **Deploy from GitHub repo** ou envie este pacote para um repositório.
2. O Railway detectará o `Dockerfile` e o `railway.json` na raiz. A configuração já define o builder Docker, o health check `/health` e a política de reinício. Caso solicite uma configuração manual, selecione Dockerfile como método de build.
3. Aguarde o build, que instala Python, dependências e Chromium pelo Playwright.
4. Em **Settings → Networking**, selecione **Generate Domain** para obter o endereço público.
5. Verifique o serviço acessando `https://SEU-DOMINIO/health`. O retorno deve conter `status: ok`.

O contêiner usa a variável `PORT` fornecida automaticamente pelo Railway. Não altere o `Dockerfile` nem o `railway.json`; eles já estão preparados para o deploy. O comando de inicialização mantém um único worker e oito threads para preservar as sessões de captura em memória.

## Domínio próprio

Em **Settings → Networking → Custom Domain**, adicione seu domínio. Depois, crie no provedor DNS o registro indicado pelo Railway, normalmente um CNAME. Aguarde a propagação e teste novamente o endpoint `/health`.

## Recursos

Para capturas de sites complexos, escolha um plano com memória suficiente para executar Chromium. Se o serviço reiniciar durante uma captura, a sessão e o ZIP temporário serão perdidos; isso é esperado nesta versão sem banco de dados externo.
