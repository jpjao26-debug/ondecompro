# OndeCompro?

App pessoal que mostra, todo dia, os preços dos mercados de Ubatuba e onde cada produto está mais barato.

- **Mercados:** Tenda (loja Ubatuba), Shibata (loja Ubatuba) e Semar (Ubatuba II – Ressaca, loja 26).
  O Semar autorizou o uso pessoal, sem fins comerciais.
- **Quando atualiza:** às 12:00. O PC principal roda de segunda a sábado e o outro PC roda aos domingos.
  Se o PC estiver desligado na hora, a coleta roda assim que ele for ligado.
- **Onde fica o app:** no GitHub Pages (gratuito). No celular é só abrir o link e tocar em "Adicionar à tela inicial".

## O que tem nesta pasta

| Arquivo / pasta | Para que serve |
|---|---|
| `instalar.bat` | Instala tudo e agenda a coleta. É só dar dois cliques. |
| `rodar_agora.bat` | Roda uma coleta na hora, sem esperar o horário. |
| `rodar.ps1` | O que o Agendador de Tarefas executa: coleta, compara e publica. |
| `coletor/` | O robô (Python): `tenda.py`, `shibata.py`, `semar.py`, `ler_encartes.py`, `comparar.py`, `publicar.py`. |
| `site/` | O app que abre no celular. |
| `dados/` | Histórico de preços e leitura dos encartes (fica guardado no GitHub). |
| `logs/` | Um resumo de cada coleta, por dia. |

## Instalação no PC principal (uma vez só)

1. **Conta no GitHub:** crie em https://github.com/signup.
2. **Repositório:** clique em **New repository** e dê o nome `ondecompro`. Marque **Public**, porque o GitHub Pages
   gratuito só funciona em repositório público. **Não** marque "Add a README". Copie o endereço que aparece
   (`https://github.com/SEU-USUARIO/ondecompro.git`).
3. **Programas:** você precisa do Python, que já tem, e do Git. Pra instalar o Git, abra o PowerShell e rode
   `winget install Git.Git`.
4. **Chave do Gemini (grátis):** entre em https://aistudio.google.com/apikey com sua conta Google →
   **Create API key** → copie. Crie um arquivo `chaves.env` **dentro da pasta do projeto** com a linha
   `GEMINI_API_KEY=sua-chave` (no Bloco de Notas, salve como "Todos os arquivos"). O valor nunca aparece em lugar nenhum.
5. Coloque esta pasta onde quiser (por exemplo `C:\Users\pedro\Desktop\OndeCompro`) e dê dois cliques em **`instalar.bat`**.
   - Escolha **1** (PC principal).
   - Cole o endereço do repositório. Na primeira vez, o Git abre uma janela pra você entrar na conta do GitHub.
   - No fim, responda **s** pra fazer a primeira coleta.
6. **Ligar o app:** no GitHub, abra o repositório → **Settings → Pages** → em *Branch*, escolha **gh-pages** e
   **/(root)** → **Save**. Em 1–2 minutos aparece o link (`https://SEU-USUARIO.github.io/ondecompro/`).

## Instalação no outro PC (domingos)

1. Instale Python e Git nele.
2. Abra o PowerShell na pasta onde quer guardar o projeto e rode
   `git clone https://github.com/SEU-USUARIO/ondecompro.git`.
3. Coloque um `chaves.env` com a mesma linha `GEMINI_API_KEY=...` dentro da pasta `ondecompro` desse PC.
4. Entre na pasta `ondecompro`, dê dois cliques em **`instalar.bat`** e escolha **2**.

Os dois PCs leem e gravam o histórico no mesmo repositório, então um sempre continua de onde o outro parou.

## No celular (Android)

1. Abra o link do GitHub Pages no Chrome.
2. Menu ⋮ → **Adicionar à tela inicial** (ou **Instalar app**).
3. Pronto: o ícone **OndeCompro?** abre como app. Os corações (favoritos) ficam salvos em cada celular.

## Se algo der errado

- Abra a pasta `logs` e veja o arquivo do dia.
- Se um mercado falhar, o app continua com os preços da coleta anterior dele.
- Pra rodar na hora: dois cliques em `rodar_agora.bat`.
- Pra mudar o horário: Agendador de Tarefas do Windows → tarefa **OndeCompro** → Gatilhos.
