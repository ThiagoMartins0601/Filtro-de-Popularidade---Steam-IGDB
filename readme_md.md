# Pipeline de Inteligencia de Mercado e Analise de Redes de Jogos

Este repositorio contem um pipeline de engenharia de dados em Python voltado para a extracao, processamento, analise estatistica (Bayesiana) e modelagem de grafos de similaridade de jogos com base em metadados da Steam, IGDB e avaliacoes de usuarios. O projeto gera visualizacoes de redes interativas e bases unificadas otimizadas para inteligencia de mercado.

---

## Estrutura do Repositorio

A organizacao atual dos arquivos na raiz do projeto segue a estrutura abaixo:

* **`Dados Numericos/`**: Diretorio destinado aos arquivos de dados brutos, bases intermediarias e saidas processadas em JSON.
* **`grafo.py`**: Script responsavel pela construcao do grafo de similaridade em `networkx`, execucao do algoritmo de Dijkstra para centralidade de rede, classificacao dos Tiers e geracao da visualizacao interativa em HTML.
* **`heuristica.py`**: Modulo contendo as regras de pontuacao, calculo de polaridade Bayesiana, pesos de similaridade e amostragem estratificada.
* **`igdb.py` / `igdbplus.py`**: Scripts de integracao, coleta e tratamento de dados oriundos da API do IGDB.
* **`kaggle.py`**: Modulo responsavel pela leitura em blocos (via `pandas`), limpeza e indexacao otimizada ($O(1)$) das bases de dados e reviews extraidas do Kaggle.
* **`steam.py`**: Modulo de extracao, limpeza e normalizacao dos metadados da Steam.
* **`tracker_state.json`**: Arquivo de controle de estado para rastreamento de progresso das coletas e processamento.
* **`twitch_token.json`**: Arquivo de credenciais e tokens de autenticacao para acesso a API da Twitch/IGDB.
* **`README.md`**: Documentacao geral do projeto.

---

## Obtencao dos Dados Necessarios (Kaggle)

Devido as restricoes de tamanho de arquivo do GitHub, os arquivos brutos pesados (como o dataset de reviews e o JSON de jogos da Steam extraidos do Kaggle) nao estao inclusos no repositorio.

Para executar o pipeline localmente, baixe a base de dados oficial utilizada pelo projeto:

* **Link de Download:** [Baixe o Dataset de Jogos e Reviews da Steam no Kaggle](https://www.kaggle.com/)

### Onde posicionar os arquivos baixados
Apos realizar o download e extrair os arquivos, posicione-os dentro da pasta **`Dados Numericos/`** na raiz do projeto com os seguintes nomes:
1. `steam_games.json` (Metadados de jogos extraidos do Kaggle)
2. `dataset.csv` (Base contendo o historico completo de reviews)
3. `bancodados_completo.json` (Base legada de suporte, caso utilizada na integracao)

---

## Como Utilizar

### 1. Pre-requisitos
Certifique-se de ter o Python 3.8 ou superior instalado em seu ambiente. Instale as bibliotecas necessarias executando:

```bash
pip install pandas networkx requests
```

### 2. Fluxo de Execucao
Com os arquivos posicionados na pasta `Dados Numericos/`, execute os modulos conforme a etapa desejada:

1. **Coleta e Enriquecimento (Opcional, caso precise atualizar dados via API):**
   Execute os scripts `steam.py`, `igdb.py` ou `igdbplus.py` garantindo que o `twitch_token.json` esteja configurado.
2. **Processamento e Indexacao do Dataset:**
   Execute o processamento de reviews e cruzamento de dados com `kaggle.py` (utilize a flag `-u` para visualizar os logs em tempo real no terminal):
   ```bash
   python -u kaggle.py
   ```
3. **Geracao do Grafo e Visualizacao:**
   Execute o script de modelagem de rede e heuristicas para gerar os arquivos finais:
   ```bash
   python -u grafo.py
   ```

### 3. Saidas Geradas
Ao finalizar o processamento, os seguintes arquivos serao gerados:
* `Dados Numericos/bancodados_comparativo_final.json`: Base unificada de mercado processada com metricas Bayesianas e classificacao de Tiers (0 a 4).
* `Dados Numericos/frequencia_reviews.json`: Base isolada contendo o mapeamento de palavras-chave positivas e negativas mais frequentes por jogo.
* `rede_inteligencia_mercado.html`: Dashboard grafico interativo (contendo os principais hubs de mercado com fisica estabilizada e painel inspetor lateral para consulta do JSON de reviews).

---

## Compatibilidade entre Sistemas (Windows e Linux)

O codigo e totalmente compativel com sistemas operacionais baseados em Unix (Linux / Ubuntu Server) e Windows, utilizando o modulo `os.path` para o gerenciamento de caminhos de diretorios.

Pontos de atencao para execucao em ambientes Linux:
* **Sensibilidade a maiusculas e minusculas (Case Sensitivity):** Certifique-se de que o nome da pasta `Dados Numericos` e dos arquivos (`dataset.csv`, `steam_games.json`, `bancodados_completo.json`) correspondem exatamente a grafia esperada pelos scripts.
* **Codificacao de caracteres:** Todas as rotinas de leitura e escrita utilizam explicitamente `utf-8` e `utf-8-sig`, evitando erros de decodificacao de acentuacao e caracteres especiais.