# Instalação e atualização

1. Crie ambiente virtual e instale o projeto com `python -m pip install -e .`
   (ou `python -m pip install .` para instalar a wheel).
2. Execute `vendedor doctor` para diagnosticar Python, SQLite, diretório
   privado, skills, modelo e Farol.
3. Execute `vendedor examples` ou importe um pacote validado.
4. Rode `vendedor validate` antes de habilitar atendimento.

Para desenvolvimento, instale o extra de testes com `python -m pip install -e ".[dev]"` e execute `python -m pytest -q`.

Os packs de skills, referências, schemas e atribuições também são incluídos na
wheel em `share/vendedor-adaptavel/`. O código instalado é separado dos dados em `.vendedor-data/`. O SQLite contém
pacotes, conversas, eventos, efeitos idempotentes, outbox, inventário,
checkpoint e fontes. Não coloque segredos no pacote; o adaptador HTTP lê a chave
somente de `SELLER_MODEL_API_KEY` em tempo de execução.

Atualizações do código não sobrescrevem a base. Faça backup do diretório privado
antes de migrar; a avaliação de recuperação usa cópia da base e IDs
idempotentes. Uma alteração de política deve ser validada novamente e ter uma
versão de pacote promovida explicitamente.
