# MIIU · Visão computacional (YOLOv8)

Pipeline do dataset ao modelo publicado no backend. Rode tudo a partir da
pasta `miiu\`, com o venv do backend ativo.

```
ml/raw/        fontes originais (Roboflow e fotos próprias)
ml/work/       fontes consolidadas por classe (consolidar.py)
ml/dataset/    treino/val/teste prontos para o YOLO (dividir.py)
ml/runs/       execuções de treinamento, com curvas e gráficos (treinar.py)
ml/resultados/ métricas no conjunto de teste (avaliar.py)
```

## 1. Consolidar (já feito para os dados públicos)

```powershell
python ml\scripts\consolidar.py buraco
python ml\scripts\consolidar.py calcada_danificada
```

Mesmas regras do script original: resolução mínima de 512 px, deduplicação
por SHA-256, remapeamento dos índices (0 = buraco, 1 = calçada danificada),
prefixo de proveniência e `manifesto.csv`. O `pothole_bradwyer` continua fora
(licença ODbL).

**Fotos próprias de Teresina.** Rotule no Roboflow com as classes `buraco` e
`calcada_danificada`, exporte no formato YOLOv8, descompacte em
`ml\raw\proprias\` e rode:

```powershell
python ml\scripts\consolidar.py proprias
```

O mapeamento é feito pelo nome da classe lido do `data.yaml`, então a ordem
das classes no Roboflow não importa.

## 2. Dividir sem vazamento

```powershell
python ml\scripts\dividir.py
```

O Roboflow exportou cerca de quatro versões aumentadas de cada foto: as 2.825
imagens consolidadas vêm de apenas 713 fotos originais (444 de buraco e 269
de calçada). Dividir por arquivo colocaria versões da mesma foto no treino e
no teste, e as métricas ficariam infladas. Por isso o script:

1. divide por **grupo** (a foto original, identificada pelo nome antes de `.rf.`);
2. estratifica por classe e origem (cada fonte contribui com 70/20/10);
3. mantém **uma imagem por grupo** em validação e teste (as versões
   aumentadas restantes ficam fora; use `--manter-aumentos` para incluí-las);
4. confere no fim que nenhum grupo e nenhum SHA-256 aparece em duas partições.

Gera `ml\dataset\data.yaml`, `divisao.csv` (imagem a imagem) e `resumo.txt`
(contagens por partição, classe e origem, para a tabela do dataset na
monografia).

## 3. Treinar na GPU

O `pip install -r requirements.txt` instala o PyTorch só para CPU, que basta
para o backend. Para treinar na RTX 4050, troque pela versão com CUDA (uma vez):

```powershell
pip uninstall -y torch torchvision
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

Se o comando falhar, gere o comando certo em
https://pytorch.org/get-started/locally/ (Windows, Pip, CUDA). Depois:

```powershell
python ml\scripts\treinar.py --epocas 3 --fracao 0.1      # teste rápido (minutos)
python ml\scripts\treinar.py                              # yolov8s, 100 épocas, paciência 25
```

Padrões para 6 GB de VRAM: imgsz 640, batch 8, precisão mista (AMP), semente
42. Se faltar memória de vídeo, use `--batch 4`; para um modelo menor,
`--modelo yolov8n.pt`. Feche o uvicorn e o Docker durante o treino.

Ao terminar, o melhor modelo é copiado para
`miiu-backend\modelos\miiu_yolov8.pt`, com um JSON ao lado (parâmetros,
épocas executadas, métricas de validação, versões de Python, PyTorch e GPU).
As curvas de perda e mAP para a monografia ficam em
`ml\runs\<execucao>\results.png`.

## 4. Avaliar no conjunto de teste

```powershell
python ml\scripts\avaliar.py
```

Dois níveis de métricas, no conjunto de teste (nunca visto no treino):

- **Detecção**: precisão, recall, F1, mAP@50 e mAP@50:95 por classe, matriz
  de confusão e curvas PR/F1 (gráficos do Ultralytics).
- **Classificação da ocorrência**, do jeito que o backend usa o modelo (classe
  da caixa de maior confiança): acurácia, precisão, recall e F1 por classe
  (meta do projeto: F1 > 80%) e a tabela de **limiar de triagem**: para cada
  limiar entre 0,10 e 0,90, quantas ocorrências seriam classificadas sem
  triagem humana e com que acerto. É o que justifica o `INFERENCIA_LIMIAR` do
  backend.

Resultados em `ml\resultados\<nome>\`: `metricas.json`,
`metricas_por_classe.csv`, `limiar.csv`, `previsoes.csv` e os gráficos.

## Versionamento

As imagens não devem ir para o Git. O `.gitignore` da raiz do projeto ignora
`ml/raw`, `ml/work`, `ml/dataset`, `ml/runs` e `ml/resultados`. Os scripts
(`ml/scripts`) e este README são versionados.
