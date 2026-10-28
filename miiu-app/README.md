# MIIU · Aplicativo do cidadão (Flutter)

Reporte com foto e localização automática, número de protocolo para
acompanhar, mapa das ocorrências validadas e alertas de proximidade
(geofencing). Sem cadastro: o aparelho é identificado por um código aleatório.

## Primeira execução

Esta pasta traz só o código (`lib/`, `test/`, `pubspec.yaml`). A pasta
`android/` é gerada pelo próprio Flutter. No PowerShell:

```powershell
cd C:\Users\"Marcio Felipe"\miiu\miiu-app

flutter create --org br.uespi.miiu --project-name miiu_app --platforms android .
python tools\configurar_android.py
flutter pub get
flutter test
flutter run
```

- O `flutter create .` não sobrescreve os arquivos que já existem; ele só
  cria o que falta (pasta `android/` e afins).
- O `configurar_android.py` adiciona as permissões (internet, localização,
  serviço em primeiro plano, notificações), libera HTTP para o servidor local
  e ajusta o `minSdk` para 23. Pode rodar de novo sem problema.
- O `flutter test` confere que o app entende o JSON da API (as amostras do
  teste foram geradas pelo backend real).

## Endereço do servidor

O app vem apontado para `http://10.0.2.2:8000`, que é o `localhost` do
computador visto de dentro do **emulador** Android. Em um **celular físico**:

1. Rode o backend com `--host 0.0.0.0` (veja o README do backend).
2. Descubra o IP do computador: `ipconfig`, linha "Endereço IPv4" do Wi-Fi.
3. No app, aba **Ajustes**: `http://SEU_IP:8000` > "Salvar e testar conexão".

Celular e computador precisam estar na mesma rede Wi-Fi.

## Telas

- **Mapa**: ocorrências validadas num raio de 5 km, com o círculo da
  geocerca; chave "Alertas de proximidade"; botão "Reportar problema".
- **Reportar**: tirar a foto, localização automática com a precisão do GPS,
  escolher "Buraco na via" ou "Calçada danificada", descrição opcional. Ao
  enviar, mostra o protocolo e a análise automática da foto. Na versão de
  desenvolvimento (`flutter run`) aparece também o botão "Galeria (teste)",
  para usar fotos do dataset no emulador; na versão final só vale a câmera.
- **Meus reportes**: protocolos deste aparelho com o status atualizado,
  consulta de qualquer protocolo e histórico de andamento.
- **Ajustes**: endereço do servidor, alertas, situação do push e privacidade.

## Alertas de proximidade

Com a chave ligada, o app acompanha o GPS e, a cada deslocamento relevante
(15 m, no máximo uma consulta a cada 10 s salvo deslocamento de 25 m),
pergunta ao backend se entrou em alguma geocerca. No Android a leitura
continua com o app em segundo plano, por um serviço em primeiro plano que
mostra uma notificação fixa enquanto os alertas estiverem ligados.

- **App aberto**: o alerta aparece como faixa no topo, com vibração, e o
  botão "Ver no mapa".
- **App em segundo plano**: o alerta chega como notificação push, se o
  Firebase estiver configurado (abaixo). Sem ele, o alerta aparece quando o
  app volta para a tela.

Para testar no emulador: rode a simulação ou valide uma ocorrência pelo
painel, e no emulador abra "..." > Location e mova o ponto para perto dela.

## Notificações push (opcional)

Sem Firebase o app funciona normalmente. Para o push com o app fechado:

```powershell
npm install -g firebase-tools
firebase login
dart pub global activate flutterfire_cli
flutterfire configure
```

Escolha o projeto criado no console e a plataforma Android. O comando
substitui `lib/firebase_options.dart` (hoje um substituto vazio) e configura o
Gradle. Configure também o backend com a chave da conta de serviço (veja o
README do backend). Em Ajustes, o app passa a mostrar "Notificações push
ativas".

## Estrutura

```
lib/
  main.dart               navegação e exibição dos alertas
  modelos.dart            JSON da API
  rotulos.dart            textos, cores e formatação
  estado.dart             sinais compartilhados entre as telas
  firebase_options.dart   substituído pelo flutterfire configure
  servicos/               api, armazenamento, localizacao, geocerca, push
  telas/                  inicio, reportar, minhas, detalhe, configuracoes
  widgets/                selo de status e marcadores do mapa
test/widget_test.dart     contrato com a API e formatação
tools/configurar_android.py
```
