# Sobre a publicação — FinTrack

Este repositório foi preparado para um portfólio de desenvolvimento. Antes de publicar na internet ou atender clientes reais, consulte as seções de segurança e produção no README e na pasta `docs/`.

- **Código-fonte:** Python, FastAPI, SQLAlchemy, HTML, CSS e JavaScript.
- **Capturas:** pasta `previews/`, com dados demonstrativos.
- **Arquivos privados:** `.env`, ambientes virtuais e bancos de dados não devem ser versionados.
- **Visibilidade recomendada para o portfólio:** público, com revisão prévia do conteúdo.
- **Licença:** nenhuma licença de redistribuição adicionada automaticamente; o proprietário decide a licença.
- **Endereço do código após publicação:** https://github.com/tteukkkk/fintrack

## Demonstração estática no GitHub Pages

O arquivo `index.html` da raiz contém uma **demonstração visual responsiva** do projeto, com capturas da pasta `previews/`, modo claro/escuro e ampliação de imagens. **Não é a aplicação FastAPI em funcionamento**: autenticação, APIs e banco de dados não funcionam no GitHub Pages.

Para habilitar a publicação, acesse [Settings → Pages](https://github.com/tteukkkk/fintrack/settings/pages), selecione **Deploy from a branch**, escolha **main** e **/(root)** e clique em **Save**. Depois que a implantação terminar, o endereço esperado será:

https://tteukkkk.github.io/fintrack/

Para disponibilizar as funcionalidades reais, será preciso hospedar o backend em um serviço compatível com Python e configurar um banco de dados persistente, segurança e variáveis de ambiente.
