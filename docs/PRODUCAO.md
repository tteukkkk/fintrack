# Checklist para implantação real

**Esta versão é para demonstração e avaliação profissional. Não a classifique como plataforma financeira validada para produção.**

## Bloqueadores antes de receber dados financeiros reais

- [ ] Hospedagem em ambiente com HTTPS, domínio, certificados válidos e isolamento de rede.
- [ ] PostgreSQL gerenciado com backup criptografado automático, testes de restauração e retenção documentada.
- [ ] Migrações Alembic versionadas, reversíveis e testadas em staging.
- [ ] Configurar `FINTRACK_HTTPS_ONLY=1` atrás de proxy HTTPS de confiança, cookies seguros e headers de segurança (CSP, HSTS, Permissions-Policy etc.).
- [ ] Implementar recuperação de senha com verificação de e-mail, expiração de tokens, 2FA opcional e revogação de sessões.
- [ ] Rate limit distribuído (por exemplo, Redis + gateway/WAF), alertas de abusos e proteção antiautomação.
- [ ] Rever autenticação, autorização, injeções, XSS, CSRF, importação de arquivos e limites de recursos em auditoria independente.
- [ ] Testar concorrência de importação e geração de recorrências sob múltiplas instâncias e transações isoladas.
- [ ] Logs estruturados com redaction de dados pessoais, métricas, alertas, SLOs e processo de incidentes.
- [ ] Política de privacidade, retenção, exclusão de dados e adequação à LGPD para finalidade, consentimento quando necessário e atendimento dos titulares.
- [ ] Revisar termos de uso, suporte, operação, capacidade e custos de infraestrutura.
- [ ] Cobertura de testes de integração e e2e em browsers, acessibilidade WCAG, testes de carga e revisão responsiva em dispositivos reais.
- [ ] Revisar vulnerabilidades e atualizar dependências; automatizar CI/CD e publicação com rollback.

## O que está realmente implementado

A plataforma já permite operações locais com cadastro, autenticação, sessões, separação de espaços, receitas/despesas, orçamentos, metas virtuais, recorrências manuais, relatórios e CSV. Os **26 testes de API** foram executados no ambiente de desenvolvimento; a interface também passou por um **smoke test interativo** conectado à API via TestClient. Isso **não** comprova resistência a ataques ou confiabilidade operacional em produção.

## Hospedagem

GitHub Pages oferece conteúdo estático e **não** hospeda FastAPI. Utilize uma hospedagem de aplicações Python com processo persistente, PostgreSQL e TLS. O `Dockerfile` e `compose.example.yaml` são destinados a desenvolvimento local e não devem ser expostos diretamente na internet sem o endurecimento acima.
